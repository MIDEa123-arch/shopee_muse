import logging
import math
import random
import re
import time
from collections import Counter, OrderedDict
from threading import Lock
from fastapi import HTTPException
from app.database import connection,public_product
from app.services.cart import cart_rows
from app.services.shipping import shipping_groups
from app import config
from .evaluation import evaluation_summary
from .catalog import curated_demo_titles,product_kind,has_matching_demo_photo
from app.native_catalog import catalog_info,MODE
from .native import native_ranking
from .merchandise import (kind as merchandise_kind, identity, COMPLEMENTS,
                          is_complement, purchase_context, exclude_owned, unique_models)


def diversify(ranked, intent_caps=None):
    """Keep a stable, varied list without repeating a product name or duplicating photos adjacent to each other,
    while allowing high-intent categories to occupy a larger share of the feed."""
    result = []
    photo_counts = {}
    names = set()
    intent_caps = intent_caps or {}
    last_photo = None
    while ranked:
        categories = {}
        deferred = []
        for product, score in ranked:
            category = product['category_id']
            photo = product.get('image_url') or product['id']
            name = product['name'].casefold().strip()
            if name in names:
                continue
            # Allow at most 2 items with the same photo across the feed, avoiding identical consecutive photos
            if photo_counts.get(photo, 0) >= 2 or (photo == last_photo and len(result) > 0):
                deferred.append((product, score))
                continue
            max_cat = intent_caps.get(category, 3)
            if categories.get(category, 0) >= max_cat:
                deferred.append((product, score))
                continue
            photo_counts[photo] = photo_counts.get(photo, 0) + 1
            last_photo = photo
            names.add(name)
            categories[category] = categories.get(category, 0) + 1
            result.append((product, score))
        if not deferred or len(deferred) == len(ranked):
            # If no items could be added without violation, add remaining unique names
            for product, score in deferred:
                name = product['name'].casefold().strip()
                if name not in names:
                    names.add(name)
                    result.append((product, score))
            break
        ranked = deferred
    return result


ACTION_WEIGHTS = {'demo_interest': 8.0, 'purchase': 5.0, 'add_to_cart': 4.0, 'favorite': 3.0, 'click': 2.0}


def include_category_candidates(products, selected_ids, category_id, limit=24):
    """Include top rated candidates from a category of interest."""
    if not category_id:
        return selected_ids
    photo_counts = {}
    added = 0
    candidates = sorted((p for p in products if p['category_id'] == category_id),
                        key=lambda p: (p['rating_star'], p['sold_count']), reverse=True)
    for product in candidates:
        image = product.get('image_url') or product['id']
        if photo_counts.get(image, 0) >= 2:
            continue
        photo_counts[image] = photo_counts.get(image, 0) + 1
        selected_ids.add(product['raw_item_id'])
        added += 1
        if added >= limit:
            break
    return selected_ids


def apply_customer_intent(ranked, signals):
    """Combine base model rank with real recent session actions and allocate feed share."""
    if not ranked:
        return ranked, [], {}
    strengths = {}
    names = {}
    kind_strengths = {}
    for index, row in enumerate(signals):
        category = row['category_id']
        weight = ACTION_WEIGHTS.get(row['action_type'], 1.0) * (0.86**index)
        strengths[category] = strengths.get(category, 0) + weight
        names[category] = row.get('category_name') or f"Danh mục {category}"
        prod_name = row.get('product_name') or ''
        kind = product_kind(prod_name)
        if kind:
            kind_strengths[kind] = kind_strengths.get(kind, 0) + weight
    if not strengths:
        for product, _ in ranked:
            product.setdefault('recommendation_reason', 'Gợi ý dành cho bạn')
        return ranked, [], {}
    peak = max(strengths.values())
    peak_kind = max(kind_strengths.values()) if kind_strengths else 0
    count = max(1, len(ranked) - 1)
    rescored = []
    for base_index, (product, model_score) in enumerate(ranked):
        category = product['category_id']
        p_kind = product_kind(product['name'])
        base_rank = 1 - (base_index / count)
        cat_intent = strengths.get(category, 0) / peak
        kind_intent = (kind_strengths.get(p_kind, 0) / peak_kind) if peak_kind and p_kind else 0
        display_rank = base_rank + 1.5 * cat_intent + 1.2 * kind_intent
        if kind_intent > 0.25:
            product['recommendation_reason'] = f"Gợi ý theo sự quan tâm về {p_kind.title()}"
        elif cat_intent > 0.15:
            product['recommendation_reason'] = f"Hợp với hoạt động gần đây về {names[category]}"
        else:
            product['recommendation_reason'] = 'Gợi ý dành cho bạn'
        rescored.append((product, model_score, display_rank))
    rescored.sort(key=lambda row: (row[2], row[1], row[0]['sold_count']), reverse=True)
    summary = [{'category_id': category, 'category_name': names[category], 'strength': round(value / peak, 3)}
               for category, value in sorted(strengths.items(), key=lambda pair: pair[1], reverse=True)]

    # Dynamic feed quota: high-intent categories receive up to 14 items out of 24
    intent_caps = {}
    for s in summary:
        cid = s['category_id']
        st = s['strength']
        if st >= 0.65:
            intent_caps[cid] = 14
        elif st >= 0.4:
            intent_caps[cid] = 8
        elif st >= 0.2:
            intent_caps[cid] = 5
        else:
            intent_caps[cid] = 3

    return [(product, score) for product, score, _ in rescored], summary, intent_caps


COMPLEMENTARY_MAP = {
    1: [1, 2, 8, 9],  # Điện tử -> Phụ kiện điện tử, Âm thanh, Balo/Phụ kiện, Điện thoại
    2: [2, 1, 9, 8],  # Âm thanh -> Điện tử, Điện thoại, Phụ kiện
    3: [3, 5, 8],     # Thời trang nam -> Quần/Áo nam, Giày dép, Phụ kiện (đồng hồ, ví)
    4: [4, 5, 7, 8],  # Thời trang nữ -> Đầm/Váy/Áo nữ, Giày cao gót, Mỹ phẩm, Phụ kiện
    5: [5, 11, 3, 8], # Giày dép -> Thể thao, Giày dép, Phụ kiện
    6: [6, 8],        # Gia dụng thông minh -> Đồ gia dụng khác, Phụ kiện nhà cửa
    7: [7, 4, 8],     # Mỹ phẩm -> Các bước skincare khác, Thời trang nữ, Phụ kiện
    8: [8, 3, 4, 1],  # Phụ kiện -> Thời trang, Công nghệ
    9: [9, 2, 1, 8],  # Điện thoại & Tablet -> Âm thanh/Tai nghe, Phụ kiện điện tử
    10: [10, 6, 11],  # Đồ chơi & Trẻ Em -> Đồ chơi, Gia dụng, Dã ngoại
    11: [11, 5, 8],   # Thể thao & Dã ngoại -> Thể thao, Giày dép, Trang phục
}

CATEGORY_COMPLEMENTS = {
    1: ('tai nghe', 'bàn phím', 'chuột', 'màn hình', 'củ sạc', 'cáp sạc', 'pin dự phòng', 'balo', 'lót chuột'),
    2: ('củ sạc', 'cáp sạc', 'pin dự phòng', 'sạc', 'túi đựng', 'đệm tai', 'giá đỡ'),
    3: ('đồng hồ', 'ví da', 'thắt lưng', 'kính', 'giày', 'tất'),
    4: ('túi xách', 'son', 'serum', 'kem', 'kính', 'giày'),
    5: ('vớ', 'tất', 'bình nước', 'thảm tập', 'thể thao', 'kháng lực', 'dây giày', 'lót'),
    6: ('chảo', 'hộp cơm', 'máy xay', 'bình giữ nhiệt', 'bàn ủi', 'khăn lau', 'giấy nến', 'kẹp', 'dao'),
    7: ('kem chống nắng', 'serum', 'son', 'nước tẩy trang', 'sữa rửa mặt', 'mặt nạ', 'bông'),
    8: ('hộp đựng', 'khăn lau', 'dây da', 'ví da'),
    9: ('tai nghe', 'củ sạc', 'cáp sạc', 'pin dự phòng', 'sạc', 'ốp', 'bao da'),
    10: ('khăn ướt', 'bình sữa', 'sữa', 'đồ chơi'),
    11: ('thảm tập', 'con lăn', 'dây kháng lực', 'bình nước', 'túi thể thao'),
}


def core_product_title(name: str) -> str:
    return identity({'name': name})


def build_shopee_feed(ranked, signals, limit=24, retail=False):
    """Build a balanced, harmonious Shopee/Taobao style feed:
    - High-intent items (sub-kind or category): ~4-5 items (approx 20% of feed)
    - Complementary cross-category items: ~3 items
    - Diverse lifestyle & popular discovery: ~16 items across various categories
    - Interleaved smoothly across the feed (no continuous wall of identical items)
    - Exploration jitter so every page reload rotates fresh discoveries
    - Deduplication strictly by core product name (no photo filtering restriction)
    """
    if not ranked:
        return [], []

    # 1. Deduplicate candidates by product name & core title, apply subtle exploration jitter for reload freshness
    unique_candidates = []
    seen_names = set()
    seen_cores = set()
    for product, score in ranked:
        name = product['name'].strip().casefold()
        core = core_product_title(product['name'])
        if name in seen_names or (core and core in seen_cores):
            continue
        seen_names.add(name)
        if core:
            seen_cores.add(core)
        jitter = 0 if retail else random.uniform(-0.04, 0.04)
        unique_candidates.append((product, score + jitter))

    # 2. Extract recent customer intent
    strengths = {}
    names = {}
    kind_strengths = {}
    for index, row in enumerate(signals or []):
        cat = row['category_id']
        weight = ACTION_WEIGHTS.get(row['action_type'], 1.0) * (0.86**index)
        strengths[cat] = strengths.get(cat, 0) + weight
        names[cat] = row.get('category_name') or f"Danh mục {cat}"
        p_name = row.get('product_name') or ''
        k = merchandise_kind({'name':p_name}) if retail else product_kind(p_name)
        target_types=COMPLEMENTS.get(k,set()) if retail and row['action_type']=='purchase' else {k}
        for target_type in sorted(target_types):
            if target_type:
                kind_strengths[target_type] = kind_strengths.get(target_type, 0) + weight

    intent_cat = max(strengths, key=strengths.get) if strengths else None
    intent_kind = max(kind_strengths, key=kind_strengths.get) if kind_strengths else None
    comp_cats = set(COMPLEMENTARY_MAP.get(intent_cat, [])) - {intent_cat} if intent_cat else set()

    # 3. Partition candidates into 3 distinct pools
    intent_pool = []
    comp_pool = []
    explore_pool = []

    for product, score in unique_candidates:
        cid = product['category_id']
        p_kind = merchandise_kind(product) if retail else product_kind(product['name'])

        if intent_cat and ((not retail and cid == intent_cat) or (intent_kind and p_kind == intent_kind)):
            if intent_kind and p_kind == intent_kind:
                product['recommendation_reason'] = f"Gợi ý theo sở thích về {intent_kind.title()}"
                intent_pool.append((product, score))
            else:
                product['recommendation_reason'] = f"Hợp với hoạt động gần đây về {names.get(cid, '')}"
                intent_pool.append((product, score))
        elif (any(is_complement(product,{'name':s['product_name'],'price':s.get('product_price',10000000)})
                  for s in signals[:8] if s.get('product_name')) if retail else cid in comp_cats):
            product['recommendation_reason'] = "Phụ kiện & gợi ý phối hợp phù hợp"
            comp_pool.append((product, score))
        else:
            product['recommendation_reason'] = "Gợi ý thịnh hành hôm nay"
            explore_pool.append((product, score))

    intent_pool.sort(key=lambda x: x[1], reverse=True)
    comp_pool.sort(key=lambda x: x[1], reverse=True)
    explore_pool.sort(key=lambda x: x[1], reverse=True)

    # 4. Balanced Quotas: ~4-5 intent items (20%), ~3 complementary, remainder explore
    intent_target = min(5, len(intent_pool)) if intent_cat else 0
    comp_target = min(3, len(comp_pool)) if comp_cats else 0

    # Interleaving schedule: 'I'=Intent, 'C'=Complementary, 'E'=Explore
    schedule = [
        'I', 'E', 'C', 'E',
        'I', 'E', 'E', 'C',
        'I', 'E', 'E', 'E',
        'I', 'E', 'C', 'E',
        'I', 'E', 'E', 'E',
        'E', 'E', 'E', 'E',
        'E', 'E', 'E', 'E',
        'E', 'E', 'E', 'E'
    ]

    feed = []
    feed_names = set()
    feed_cores = set()
    explore_cat_count = Counter()
    intent_idx = 0
    comp_idx = 0
    explore_idx = 0

    for slot in schedule:
        chosen = None
        if slot == 'I' and intent_idx < intent_target:
            while intent_idx < len(intent_pool):
                cand = intent_pool[intent_idx][0]
                intent_idx += 1
                c_name = cand['name'].strip().casefold()
                c_core = core_product_title(cand['name'])
                if c_name not in feed_names and (not c_core or c_core not in feed_cores):
                    chosen = cand
                    break
        elif slot == 'C' and comp_idx < comp_target:
            while comp_idx < len(comp_pool):
                cand = comp_pool[comp_idx][0]
                comp_idx += 1
                c_name = cand['name'].strip().casefold()
                c_core = core_product_title(cand['name'])
                if c_name not in feed_names and (not c_core or c_core not in feed_cores):
                    chosen = cand
                    break
        else:
            # First attempt: pick explore item with category count < 2 for maximum variety
            cur_idx = explore_idx
            found = False
            while cur_idx < len(explore_pool):
                cand = explore_pool[cur_idx][0]
                c_name = cand['name'].strip().casefold()
                c_core = core_product_title(cand['name'])
                if c_name not in feed_names and (not c_core or c_core not in feed_cores):
                    if explore_cat_count[cand['category_id']] < 2:
                        chosen = cand
                        explore_cat_count[cand['category_id']] += 1
                        explore_pool.pop(cur_idx)
                        found = True
                        break
                cur_idx += 1
            if not found and explore_idx < len(explore_pool):
                while explore_idx < len(explore_pool):
                    cand = explore_pool[explore_idx][0]
                    explore_idx += 1
                    c_name = cand['name'].strip().casefold()
                    c_core = core_product_title(cand['name'])
                    if c_name not in feed_names and (not c_core or c_core not in feed_cores):
                        chosen = cand
                        explore_cat_count[cand['category_id']] += 1
                        break

        if not chosen:
            # Fallback to any remaining unused candidate
            for p, _ in unique_candidates:
                c_name = p['name'].strip().casefold()
                c_core = core_product_title(p['name'])
                if c_name not in feed_names and (not c_core or c_core not in feed_cores):
                    chosen = p
                    break

        if chosen:
            c_name = chosen['name'].strip().casefold()
            c_core = core_product_title(chosen['name'])
            feed_names.add(c_name)
            if c_core:
                feed_cores.add(c_core)
            feed.append(public_product(chosen))
            if len(feed) >= limit:
                break

    if len(feed) < limit:
        for p, _ in unique_candidates:
            c_name = p['name'].strip().casefold()
            c_core = core_product_title(p['name'])
            if c_name not in feed_names and (not c_core or c_core not in feed_cores):
                feed_names.add(c_name)
                if c_core:
                    feed_cores.add(c_core)
                feed.append(public_product(p))
                if len(feed) >= limit:
                    break

    summary = []
    if strengths:
        peak = max(strengths.values())
        summary = [{'category_id': c, 'category_name': names[c], 'strength': round(v / peak, 3)}
                   for c, v in sorted(strengths.items(), key=lambda x: x[1], reverse=True)]

    return feed, summary


class RecommendationService:
    def __init__(self):
        self.model=None
        self.error=None
        self.last_metrics=OrderedDict()
        self.metrics_lock=Lock()

    def load(self):
        self.model=None;self.error=None
        try:
            from .model import MuseModel
            model=MuseModel()
            model.predict(next(iter(model.users)),list(model.items)[:8])
            self.model=model
        except Exception as exc:
            self.error=f'{type(exc).__name__}: {exc}'
            logging.exception('MUSE unavailable; catalog fallback is explicitly labeled')

    def status(self,user_id=None):
        with self.metrics_lock:
            metrics=self.last_metrics.get(user_id,{}) if user_id else {}
        return {'ready':self.model is not None,'engine':'Alibaba MUSE / PyTorch CPU' if self.model else 'Catalog fallback',
                'checkpoint_loaded':self.model is not None,'scl_dimensions':128 if self.model else None,
                'gsu_top_k':50 if self.model else None,'history_limit':1000,
                'source':'https://github.com/alimama-tech/MUSE','last_metrics':metrics}

    def rank_search_candidates(self,user_id,candidates):
        if not self.model or not user_id or not candidates:
            return candidates
        self.model.items.register_products(candidates)
        if candidates[0].get('catalog_source') == 'taobao-mm':
            try:
                with connection() as db:
                    all_products=[dict(r) for r in db.execute('SELECT * FROM products WHERE stock>0 AND source_feature_complete=1 ORDER BY id')]
                self.model.items.register_products(all_products)
                all_products=[p for p in all_products if p['raw_item_id'] in self.model.items]
                scores,_=native_ranking.scores(self.model,user_id,all_products)
                for p in candidates:
                    if p['raw_item_id'] in scores:
                        p.update(p_click=scores[p['raw_item_id']],recommendation_source='ai',
                                 recommendation_reason='Theo lịch sử Taobao và hoạt động của bạn')
                return sorted(candidates,key=lambda p:(-p.get('p_click',-1),p['id']))
            except Exception:
                logging.exception('Native search inference unavailable')
                return candidates
        try:
            raw_ids=[c['raw_item_id'] for c in candidates if c.get('raw_item_id') in self.model.items]
            if not raw_ids:
                return candidates
            if len(raw_ids)>64:
                selected_ids=set(self.model.retrieve_gsu(user_id,raw_ids,top_k=64))
                score_candidates=[r for r in raw_ids if r in selected_ids]
            else:
                score_candidates=raw_ids
            scores,_=self.model.predict(user_id,score_candidates)
            if len(scores)!=len(score_candidates) or not all(0<=s<=1 for s in scores):
                raise RuntimeError('Invalid search prediction output')
            score_map=dict(zip(score_candidates,scores))
            for c in candidates:
                if c.get('raw_item_id') in score_map:
                    p=round(score_map[c['raw_item_id']],4)
                    c['p_click']=p
                    c['relevance_score']=p
                    c['recommendation_source']='ai'
                    c['recommendation_reason']='Phù hợp với hoạt động mua sắm gần đây'
            candidates.sort(key=lambda x:(x.get('p_click') or 0,x.get('sold_count',0)),reverse=True)
        except Exception as exc:
            logging.warning('Search re-ranking failed: %s',exc)
            for candidate in candidates:
                for key in ('p_click','relevance_score','recommendation_source','recommendation_reason'):
                    candidate.pop(key,None)
        return candidates

    def recommend(self,user_id=None,touchpoint='home',product_id=None,limit=24,category_id=None,display_category='',presentation_policy='original',focus_product_id=None,*,write_logs=True):
        with connection() as db:
            cinfo=catalog_info(db)
            native=cinfo['mode']==MODE
            retail=cinfo['mode'] in ('vietnam_tiki_v1','amazon_reviews_2023_v1')
        if native:
            return native_ranking.recommend(self,user_id,touchpoint,product_id,limit,category_id,display_category=display_category,presentation_policy=presentation_policy,focus_product_id=focus_product_id,write_logs=write_logs)
        start=time.perf_counter()
        with connection() as db:
            target=db.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone() if touchpoint in ('similar','complementary') else None
            cart=cart_rows(db,user_id) if user_id else []
            purchases=purchase_context(db,user_id) if retail else {'keys':set(),'recent_kinds':set(),'items':[]}
            purchased_ids={p['id'] for p in purchases['items']}
            signals=[dict(r) for r in db.execute('''SELECT h.action_type,p.category_id,c.name category_name,p.id product_id,p.name product_name,p.price product_price
                FROM user_behavior_history h JOIN products p ON p.id=h.product_id
                JOIN categories c ON c.id=p.category_id
                WHERE h.user_id=? AND h.action_type IN ('demo_interest','click','add_to_cart','purchase','favorite')
                ORDER BY h.id DESC LIMIT 16''',(user_id,))] if user_id else []
            if retail:
                signals=[s for s in signals if s['action_type']!='purchase' or s['product_id'] in purchased_ids]
            is_million = cinfo.get('mode') in ('amazon_reviews_2023_v1', 'vietnam_tiki_v1') or bool(db.execute("SELECT 1 FROM products WHERE id > 1000 LIMIT 1").fetchone())
            if is_million:
                if category_id is not None:
                    products=[dict(r) for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.stock>0
                        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 240''', (category_id,))]
                elif target and touchpoint == 'similar':
                    products=[dict(r) for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.stock>0
                        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 240''', (target['category_id'],))]
                elif target and touchpoint == 'complementary':
                    # Product-detail add-ons come only from the target's curated
                    # merchandise neighbourhood. Unrelated recent activity must
                    # never leak into this placement.
                    pool_cats = list(dict.fromkeys(
                        COMPLEMENTARY_MAP.get(target['category_id'], [target['category_id']])
                    ))
                    products = []
                    seen_p = set()
                    for cid in pool_cats[:4]:
                        for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.id <= 50000 AND p.stock>0
                            ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 60''', (cid,)):
                            if r['id'] not in seen_p:
                                seen_p.add(r['id'])
                                products.append(dict(r))
                elif touchpoint == 'cart' and cart:
                    products = []
                    seen_p = set()
                    cart_cats = list(dict.fromkeys(i['category_id'] for i in cart if i.get('category_id')))
                    comp_cats = []
                    for cart_cat in cart_cats:
                        for cid in COMPLEMENTARY_MAP.get(cart_cat, [cart_cat]):
                            if cid not in comp_cats:
                                comp_cats.append(cid)
                    for cid in comp_cats[:8]:
                        for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.id <= 50000 AND p.stock>0
                            ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 50''', (cid,)):
                            if r['id'] not in seen_p:
                                seen_p.add(r['id'])
                                products.append(dict(r))
                else:
                    # Multi-Channel Recall: Top Global Popular + Top User Intent Categories & Kinds
                    products=[dict(r) for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.stock>0
                        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 160''')]
                    seen_p = {p['id'] for p in products}
                    intent_cats = list(dict.fromkeys(s['category_id'] for s in signals[:6]))
                    for owned in purchases['items'][:4]:
                        if owned.get('recent_purchase'):
                            for cid in COMPLEMENTARY_MAP.get(owned['category_id'],[]):
                                if cid not in intent_cats:intent_cats.append(cid)
                    for cid in intent_cats[:6]:
                        for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.stock>0
                            ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 140''', (cid,)):
                            if r['id'] not in seen_p:
                                seen_p.add(r['id'])
                                products.append(dict(r))
                    intent_kinds = [product_kind(s.get('product_name') or '') for s in signals[:4] if product_kind(s.get('product_name') or '')]
                    for kind in list(dict.fromkeys(intent_kinds))[:2]:
                        for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.id<=50000 AND p.name LIKE ? AND p.stock>0
                            ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 80''', (f'%{kind}%',)):
                            if r['id'] not in seen_p:
                                seen_p.add(r['id'])
                                products.append(dict(r))
            else:
                if category_id is not None:
                    products=[dict(r) for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.stock>0 AND p.category_id=? ORDER BY p.id''', (category_id,))]
                elif target and touchpoint in ('similar','complementary'):
                    products=[dict(r) for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.stock>0 AND p.category_id=? ORDER BY p.id''', (target['category_id'],))]
                elif touchpoint == 'cart' and cart:
                    shop_names = list({i['shop_name'] for i in cart if i.get('shop_name')})
                    if shop_names:
                        placeholders = ','.join('?' for _ in shop_names)
                        products=[dict(r) for r in db.execute(f'''SELECT p.*,pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.stock>0 AND p.shop_name IN ({placeholders}) ORDER BY p.id''', shop_names)]
                    else:
                        products=[]
                else:
                    products=[dict(r) for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.stock>0 ORDER BY p.id''')]
        if touchpoint in ('similar','complementary') and not target:
            raise HTTPException(404,'Sản phẩm không tồn tại.')
        if touchpoint=='cart' and not cart:
            products=[]
        model=self.model;metadata={};strategy='popular';engine='Catalog fallback';metric='popularity'
        if model:
            model.items.register_products(products)
            if target:
                model.items.register_products([dict(target)])
        # Expanded imported histories contain automatically assembled demo names
        # with incompatible specs. Recommend from the original coherent title set;
        # retain all products, raw IDs and histories in the database.
        if config.DEMO_MODE:
            curated=[p for p in products if p.get('catalog_source') in ('amazon-2023', 'tiki-vn') or (p['name'] in curated_demo_titles() and has_matching_demo_photo(p))]
            if curated:
                products=curated
                metadata['catalog_policy']='curated_demo_metadata'
        products=[p for p in products if p['id']!=product_id]
        if retail:
            products=exclude_owned(products,purchases,cart if touchpoint in ('home','cart') else (),
                                   home=touchpoint=='home',manual_category=category_id is not None)
            metadata['purchase_policy']={'excluded_models':len(purchases['keys']),
                'recent_durable_types':sorted(purchases['recent_kinds']),
                'durable_cooldown_days':30,'cancelled_orders_excluded':True}
            if target:
                products=[p for p in products if identity(p)!=identity(dict(target))]
        if touchpoint=='home':
            recent_ids={row['product_id'] for row in signals if row['action_type'] in ('click','add_to_cart','purchase')}
            products=[p for p in products if p['id'] not in recent_ids]
        if touchpoint=='similar':
            products=[p for p in products if p['category_id']==target['category_id']]
            band=[p for p in products if target['price']*.5<=p['price']<=target['price']*2]
            if band or retail:
                products=band
            metadata['context_policy']='same_category_price_band' if band else 'same_category'
            same_kind=[p for p in products if (merchandise_kind(p)==merchandise_kind(dict(target)) if retail
                      else product_kind(p['name'])==product_kind(target['name']))]
            if same_kind or retail:
                products=same_kind
                metadata['context_policy']='same_kind_price_band' if band else 'same_kind'
            alternatives=[p for p in products if p['image_url']!=target['image_url']]
            if alternatives:
                products=alternatives
            for p in products:
                p['recommendation_reason']=('Cùng loại sản phẩm' if same_kind else 'Cùng danh mục')+(' · Giá tương đương' if band else '')
        elif touchpoint=='complementary':
            if retail:
                products=[p for p in products if is_complement(p,dict(target))]
            # Items of the same kind already appear in "Sản phẩm tương tự".
            target_kind=product_kind(target['name'])
            others=[p for p in products if product_kind(p['name'])!=target_kind]
            if others:
                products=others
            prefixes=CATEGORY_COMPLEMENTS.get(target['category_id'])
            if prefixes:
                safe=[p for p in products if any(p['name'].casefold().startswith(prefix) for prefix in prefixes)]
                if safe:
                    products=safe
            for p in products:
                p['recommendation_reason']=f"Phụ kiện & đồ bổ trợ cho {target['name'][:30]}…"
            metadata['context_policy']='curated_complementary_categories'
        elif touchpoint=='cart':
            cart_ids={i['id'] for i in cart}
            cart_photos={i['image_url'] for i in cart if i['image_url']}
            cart_cats=list(dict.fromkeys(i['category_id'] for i in cart if i.get('category_id')))
            allowed_cats=set()
            for category in cart_cats:
                allowed_cats.update(COMPLEMENTARY_MAP.get(category,[category]))
            max_cart_price=max((i['price'] for i in cart),default=500000)
            price_cap=max(1200000,int(max_cart_price*1.5))
            products=[p for p in products if p['id'] not in cart_ids
                      and p['image_url'] not in cart_photos
                      and (not allowed_cats or p['category_id'] in allowed_cats)
                      and p['price']<=price_cap]
            if retail:
                products=[p for p in products if any(is_complement(p,item) for item in cart)]
            for p in products:
                p['recommendation_reason']='Phù hợp với sản phẩm trong giỏ'
            metadata.update({'context_policy':'curated_cart_categories',
                             'cart_categories':cart_cats,
                             'allowed_categories':sorted(allowed_cats),
                             'price_cap':price_cap})
        else:
            metadata['context_policy']='in_stock_catalog'
        mapped=[p for p in products if p['raw_item_id'] in model.items] if model else []
        if mapped:
            products=mapped
        scores=[p['sold_count'] for p in products]
        inference_start=time.perf_counter();model_used=False
        try:
            if model and mapped:
                ids=[p['raw_item_id'] for p in products]
                if touchpoint=='similar' and target['raw_item_id'] in model.items:
                    scores=model.similarities(target['raw_item_id'],ids)
                    metric='cosine_similarity';strategy='SCL cosine / GSU';engine='MUSE SCL 128D';model_used=True
                    for p,s in zip(products,scores):
                        p['similarity']=round(s,6)
                elif touchpoint=='complementary':
                    if user_id:
                        if len(products)>128:
                            raw_ids=[p['raw_item_id'] for p in products]
                            selected_ids=set(model.retrieve_gsu(user_id,raw_ids,top_k=128))
                            products=[p for p in products if p['raw_item_id'] in selected_ids]
                        ids=[p['raw_item_id'] for p in products]
                        scores,extra=model.predict(user_id,ids)
                        metadata.update(extra);metric='p_click';strategy='MUSE P(click) theo lịch sử hành vi';engine='Alibaba MUSE';model_used=True
                        for p,s in zip(products,scores):
                            p['p_click']=round(s,7)
                    elif target and target['raw_item_id'] in model.items:
                        scores=model.similarities(target['raw_item_id'],ids)
                        metric='cosine_similarity';strategy='MUSE SCL cosine';engine='MUSE SCL 128D';model_used=True
                        for p,s in zip(products,scores):
                            p['similarity']=round(s,6)
                elif user_id and touchpoint not in ('similar','complementary'):
                    if len(products)>128:
                        raw_ids=[p['raw_item_id'] for p in products]
                        selected_ids=set(model.retrieve_gsu(user_id,raw_ids,top_k=128))
                        # Retain alternatives for each available photo so the
                        # final feed can stay diverse without repeating cards.
                        representatives={}
                        for p in sorted(products,key=lambda p:(p['rating_star'],p['sold_count']),reverse=True):
                            representatives.setdefault(p['image_url'] or p['id'],p['raw_item_id'])
                        selected_ids.update(list(representatives.values())[:64])
                        for category in list(dict.fromkeys(row['category_id'] for row in signals[:6]))[:3]:
                            selected_ids=include_category_candidates(products,selected_ids,category)
                        products=[p for p in products if p['raw_item_id'] in selected_ids]
                    ids=[p['raw_item_id'] for p in products]
                    scores,extra=model.predict(user_id,ids)
                    metadata.update(extra);metric='p_click';strategy='GSU (SCL Top-128) → SimTier + SA-TA → ESU';engine='Alibaba MUSE';model_used=True
                    for p,s in zip(products,scores):
                        p['p_click']=round(s,7)
                elif not user_id:
                    engine='Popular / guest'
                    for p in products:
                        p['recommendation_reason']='Sản phẩm bán chạy nổi bật'
            if len(scores)!=len(products) or not all(math.isfinite(s) for s in scores):
                raise RuntimeError('Invalid recommendation scores')
        except Exception:
            logging.exception('Recommendation inference failed; serving explicit popularity fallback')
            scores=[p['sold_count'] for p in products]
            for p in products:
                p.pop('p_click',None);p.pop('similarity',None)
            metric='popularity';strategy='popular';engine='Catalog fallback';model_used=False
            metadata['fallback_reason']='inference_failed'
        if not model_used:
            metadata.setdefault('fallback_reason','guest' if not user_id else 'model_unavailable' if not model else 'no_model_candidates')
            for p in products:
                p.setdefault('recommendation_reason','Sản phẩm bán chạy trong danh mục')
        for p in products:
            p['recommendation_source']='ai' if model_used else 'catalog'
        inference_ms=(time.perf_counter()-inference_start)*1000
        ranked=sorted(zip(products,scores),key=lambda x:(x[1],x[0]['sold_count'],-x[0]['id']),reverse=True)
        if retail:
            score_by_id={p['id']:score for p,score in ranked}
            visible=[public_product(p) for p,_ in ranked]
            visible=[p for p in visible if p.get('image_url')!='/static/images/placeholder.svg']
            visible=unique_models(visible,exclude=[public_product(target)] if target else [])
            ranked=[(p,score_by_id[p['id']]) for p in visible]
        intent_summary = []
        if touchpoint == 'home':
            feed_signals=list(signals)
            if retail:
                recent_signal_ids={s['product_id'] for s in signals}
                for owned in purchases['items'][:4]:
                    if owned.get('recent_purchase') and owned['id'] not in recent_signal_ids:
                        feed_signals.append({'action_type':'purchase','category_id':owned['category_id'],
                            'product_id':owned['id'],'product_name':owned['name'],'product_price':owned['price'],
                            'category_name':f"Danh mục {owned['category_id']}"})
            top, intent_summary = build_shopee_feed(ranked, feed_signals, limit=limit, retail=retail)
            if retail:
                just_bought=[p for p in purchases['items'][:4] if p.get('hot_purchase')]
                accessories=[p for p,_ in ranked if any(is_complement(p,owned) for owned in just_bought)][:3]
                top=unique_models(accessories+top)[:limit]
                metadata['post_purchase_accessories']=len(accessories)
        else:
            top = []
            visible_names = set()
            for product, _ in ranked:
                item = public_product(product)
                name = item['name'].strip().casefold()
                if name in visible_names:
                    continue
                visible_names.add(name)
                top.append(item)
                if len(top) >= limit:
                    break
        if retail:
            top=unique_models(top,exclude=[dict(target)] if target else [])
            top=[p for p in top if p.get('image_url')!='/static/images/placeholder.svg']
        active_interest=next(({'category_id':row['category_id'],'category_name':row['category_name'],
                               'product_id':row['product_id']} for row in signals
                              if row['action_type']=='demo_interest'),None)
        metadata.update({'engine':engine,'strategy':strategy,'score_type':metric,'candidate_count':len(products),
                         'inference_ms':round(inference_ms,2),'latency_ms':round((time.perf_counter()-start)*1000,2),
                         'checkpoint_loaded':model is not None,'model_used':model_used,'touchpoint':touchpoint,
                         'ranking_policy':'model_rank_with_recent_intent_and_diversity' if touchpoint=='home' and user_id else 'score_order_with_photo_and_category_diversity',
                         'has_more':len(ranked)>limit,'active_interest':active_interest,
                         'intent_summary':intent_summary})
        if user_id and write_logs:
            with self.metrics_lock:
                self.last_metrics[user_id]=metadata
                self.last_metrics.move_to_end(user_id)
                while len(self.last_metrics)>128:
                    self.last_metrics.popitem(last=False)
            with connection(write=True) as db:
                db.execute('''INSERT INTO recommendation_logs(user_id,touchpoint,candidate_count,top_recommended_ids,model_name,latency_ms)
                    VALUES (?,?,?,?,?,?)''',(user_id,touchpoint,len(products),','.join(str(x['id']) for x in top),engine,metadata['latency_ms']))
        quality=evaluation_summary() if model_used and metric=='p_click' else {'available':False,'reason':'not_click_ranking'}
        return {'items':top,'meta':metadata,'quality':quality}


service=RecommendationService()
