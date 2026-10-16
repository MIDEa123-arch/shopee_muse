"""Bounded full-catalog inference for the original anonymous Taobao catalog."""
import logging
import math
import time
from collections import OrderedDict
from threading import Lock

from fastapi import HTTPException

from app import config
from app.database import connection, public_product
from .evaluation import evaluation_summary
from .experience import original_profile
from collections import Counter
from .commerce import (context_candidates, distinct_illustrations,
                       user_price_affinity, interest_profile, personalize_order, feed_candidates, mix_feed)
from app.storefront import presentation_map


class NativeRanking:
    def __init__(self):
        self.lock = Lock()
        self.cache = OrderedDict()

    @staticmethod
    def history_version(user_id):
        with connection() as db:
            return tuple(tuple(r) for r in db.execute('''SELECT id,raw_item_id,action_type
                FROM user_behavior_history WHERE user_id=?
                AND action_type IN ('click','favorite','add_to_cart','purchase')
                ORDER BY id DESC LIMIT 1000''', (user_id,)))

    def scores(self, model, user_id, products):
        ids = tuple(p['raw_item_id'] for p in products)
        version = self.history_version(user_id)
        key = (str(config.DB_PATH), id(model), user_id, ids, version)
        # Serialize model work, including cache misses from simultaneous browser requests.
        with self.lock:
            entry = self.cache.get(key)
            if entry and time.monotonic() - entry[0] < 300:
                self.cache.move_to_end(key)
                return entry[1], {**entry[2], 'ranking_cache_hit': True}
            scores, extra = model.predict(user_id, list(ids))
            if len(scores) != len(ids) or not all(math.isfinite(s) and 0 <= s <= 1 for s in scores):
                raise ValueError('Invalid checkpoint probabilities')
            score_map = dict(zip(ids, scores))
            if version == self.history_version(user_id):
                self.cache[key] = (time.monotonic(), score_map, extra)
                while len(self.cache) > 8:
                    self.cache.popitem(last=False)
            return score_map, {**extra, 'ranking_cache_hit': False}

    def recommend(self, service, user_id, touchpoint, product_id, limit, category_id=None, *, write_logs=True,display_category='',presentation_policy='original',focus_product_id=None):
        started = time.perf_counter()
        with connection() as db:
            target = db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone() if product_id else None
            if category_id is not None:
                all_products = [dict(r) for r in db.execute('''SELECT p.*,c.name category_name FROM products p
                    JOIN categories c ON c.id=p.category_id WHERE p.category_id=? AND p.stock>0
                    ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 400''', (category_id,))]
            elif target and touchpoint in ('similar', 'complementary'):
                if presentation_policy != 'original':
                    # The storefront merchandise type is independent from the
                    # anonymous source group. Build the safe same-type pool from
                    # the display catalog, then let similarity rank inside it.
                    all_products = [dict(r) for r in db.execute('''SELECT p.*,c.name category_name FROM products p
                        JOIN categories c ON c.id=p.category_id
                        JOIN product_presentations d ON d.product_id=p.id
                        WHERE p.stock>0 ORDER BY p.rating_star DESC,p.sold_count DESC,p.id ASC LIMIT 400''')]
                else:
                    target_cat = target['category_id']
                    all_products = [dict(r) for r in db.execute('''SELECT p.*,c.name category_name FROM products p
                        JOIN categories c ON c.id=p.category_id WHERE p.category_id=? AND p.stock>0
                        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 400''', (target_cat,))]
                if not any(p['id'] == target['id'] for p in all_products):
                    all_products.append(dict(target))
            else:
                all_products = [dict(r) for r in db.execute('''SELECT p.*,c.name category_name FROM products p
                    JOIN categories c ON c.id=p.category_id WHERE p.stock>0
                    ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC''')]
            display_ids = {r[0] for r in db.execute('SELECT product_id FROM product_presentations WHERE category_slug=?',(display_category,))} if display_category else None
            cart_ids = {r[0] for r in db.execute('SELECT product_id FROM cart_items WHERE user_id=?', (user_id,))} if user_id else set()
            source=original_profile(db,user_id) if user_id else None
            group_counts=Counter(source['151_2_180']) if source else Counter()
            seen_raw=set(source['150_2_180']) if source else set()
            if user_id:
                seen_raw.update(r[0] for r in db.execute('''SELECT raw_item_id FROM user_behavior_history WHERE user_id=?
                    AND action_type IN ('click','favorite','add_to_cart','purchase') ORDER BY id DESC LIMIT 1000''',(user_id,)))
            context_ids=None;context={'enabled':False}
            if presentation_policy=='feed':
                context_ids,context=feed_candidates(db,all_products,user_id,touchpoint,target,focus_product_id)
            elif presentation_policy!='original':
                context_ids,_,context=context_candidates(db,all_products,user_id,touchpoint,target,display_category,focus_product_id,presentation_policy)
            affinity_info = user_price_affinity(db, user_id) if (presentation_policy == 'browse' and user_id and touchpoint == 'home') else None
            profile = interest_profile(db, user_id, focus_product_id) if (presentation_policy == 'browse' and touchpoint == 'home') else None
        if touchpoint in ('similar', 'complementary') and not target:
            raise HTTPException(404, 'Mẫu không tồn tại.')
        products = [p for p in all_products if p['id'] != product_id
                    and (context_ids is None or p['id'] in context_ids)
                    and (display_ids is None or p['id'] in display_ids)
                    and (category_id is None or p['category_id'] == category_id)
                    and (touchpoint != 'cart' or p['id'] not in cart_ids)
                    and (touchpoint != 'home' or p['raw_item_id'] not in seen_raw)]
        model = service.model
        if model:
            model.items.register_products(all_products)
        mapped = [p for p in all_products if model and p['raw_item_id'] in model.items]
        used = False; metric = 'catalog_order'; extra = {}; engine = 'Catalog fallback'
        policy = 'original_group_filter' if category_id else 'original_catalog'
        score_map = {}
        inference = time.perf_counter()
        try:
            if context.get('enabled') and not products:
                extra['fallback_reason']='no_other_products_in_context'
            elif model and touchpoint == 'similar' and target['raw_item_id'] in model.items and model.indices(model.scl_keys,[target['raw_item_id']])[0]>0:
                eligible = [p for p in products if p['raw_item_id'] in model.items]
                # SCL ranks only the already validated same-type candidate pool.
                with self.lock:
                    values = model.similarities(target['raw_item_id'], [p['raw_item_id'] for p in eligible]) if eligible else []
                if len(values) != len(eligible) or not all(math.isfinite(s) for s in values):
                    raise ValueError('Invalid embedding similarity')
                score_map = {p['raw_item_id']: s for p, s in zip(eligible, values)}
                metric = 'cosine_similarity'; engine = 'MUSE SCL 128D'; used = bool(eligible)
                policy = 'original_scl_neighbours'
            elif model and user_id and mapped and touchpoint!='similar':
                score_map, extra = self.scores(model, user_id, mapped)
                metric = 'p_click'; engine = 'Alibaba MUSE / PyTorch CPU'; used = True
        except Exception:
            logging.exception('Native ranking failed; using explicitly labeled ID order')
            extra['fallback_reason'] = 'inference_failed'
        displays = presentation_map(str(config.DB_PATH)) if presentation_policy != 'original' else {}
        if used:
            products = [p for p in products if p['raw_item_id'] in score_map]
            if context.get('enabled') and context.get('types') and touchpoint == 'home' and not display_category and presentation_policy == 'contextual':
                types_set = set(context['types'])
                focused_items = [p for p in products if (d := displays.get(p['id'])) and d.get('presentation_type') in types_set]
                other_items = [p for p in products if not ((d := displays.get(p['id'])) and d.get('presentation_type') in types_set)]
                focused_items.sort(key=lambda p: (-score_map[p['raw_item_id']], p['id']))
                other_items.sort(key=lambda p: (-score_map[p['raw_item_id']], p['id']))
                focused_slots = min(4, len(focused_items))
                products = focused_items[:focused_slots] + other_items + focused_items[focused_slots:]
            elif profile is not None:
                products = personalize_order(products, displays, profile, affinity_info, score_map)
            else:
                products.sort(key=lambda p: (-score_map[p['raw_item_id']], p['id']))
        else:
            if context.get('enabled') and not products:
                extra.setdefault('fallback_reason','no_other_products_in_context')
            elif model and touchpoint=='similar':
                extra.setdefault('fallback_reason','target_scl_unavailable')
            extra.setdefault('fallback_reason', 'guest' if not user_id else 'model_unavailable')
            if profile is not None:
                products = personalize_order(products, displays, profile, affinity_info, None)
            elif presentation_policy == 'feed':
                products.sort(key=lambda p: (-(p.get('sold_count') or 0), p['id']))
            else:
                products.sort(key=lambda p: p['id'])
        if presentation_policy == 'feed':
            products = mix_feed(products, displays, context, touchpoint)
        before_dedup=len(products)
        if presentation_policy != 'original':
            products=distinct_illustrations(products)
        items = []
        for product in products[:limit]:
            p = public_product(product)
            p['recommendation_source'] = 'ai' if used else 'catalog'
            p['history_group_events']=group_counts.get(int(p['source_category_id']),0)
            p['recommendation_reason'] = ('Gần nhau trong đặc trưng AI' if metric == 'cosine_similarity'
                else 'Theo lịch sử Taobao và hoạt động của bạn' if used and not extra.get('cold_start')
                else 'Gợi ý khởi đầu · tiếp tục khám phá để cá nhân hóa' if used
                else 'Khám phá dữ liệu Taobao gốc')
            if used:
                p['p_click' if metric == 'p_click' else 'similarity'] = score_map[product['raw_item_id']]
            if affinity_info and affinity_info.get('tier') != 'all':
                if affinity_info['min_price'] <= p['price'] <= affinity_info['max_price']:
                    p['price_tier_match'] = True
                    p['price_tier_label'] = affinity_info['label']
            items.append(p)
        meta = {**extra, 'engine': engine, 'strategy': 'Full catalog → checkpoint score' if metric == 'p_click'
                else 'Original SCL cosine' if used else 'Stable ID order', 'score_type': metric,
                'candidate_count': len(products), 'scored_catalog_count': len(score_map),
                'inference_ms': round((time.perf_counter()-inference)*1000, 2),
                'latency_ms': round((time.perf_counter()-started)*1000, 2),
                'checkpoint_loaded': model is not None, 'model_used': used, 'touchpoint': touchpoint,
                'ranking_policy': 'commerce_interest_blend' if profile is not None else 'checkpoint_score_desc' if metric == 'p_click' else 'cosine_desc' if used else 'id_asc',
                'context_policy': policy, 'catalog_policy': 'original_taobao_ids_and_groups',
                'has_more': len(products) > limit, 'active_interest': None, 'intent_summary': [],
                'category_filter': category_id, 'commerce_simulated': True}
        if affinity_info:
            meta['price_affinity'] = affinity_info
        if profile is not None:
            meta['interest_profile'] = profile
        meta['display_category_filter']=display_category or None
        meta['presentation_policy']=presentation_policy
        meta['merchandise_context']=context
        meta['duplicate_illustrations_removed']=before_dedup-len(products)
        if context.get('enabled') and not products:
            meta['empty_reason']='no_other_products_in_context'
        meta['discovery_policy']='hide_seen_items' if touchpoint=='home' else 'context_candidates'
        meta['excluded_seen_count']=sum(p['raw_item_id'] in seen_raw for p in all_products) if touchpoint=='home' else 0
        if user_id and write_logs:
            with service.metrics_lock:
                service.last_metrics[user_id] = meta
                service.last_metrics.move_to_end(user_id)
                while len(service.last_metrics) > 128:
                    service.last_metrics.popitem(last=False)
            with connection(write=True) as db:
                db.execute('''INSERT INTO recommendation_logs(user_id,touchpoint,candidate_count,
                    top_recommended_ids,model_name,latency_ms) VALUES (?,?,?,?,?,?)''',
                    (user_id,touchpoint,len(products),','.join(str(p['id']) for p in items),engine,meta['latency_ms']))
        return {'items': items, 'meta': meta, 'quality': evaluation_summary() if used and metric == 'p_click'
                else {'available': False, 'reason': 'not_click_ranking'}}


native_ranking = NativeRanking()
