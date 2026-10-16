import logging
import math
import random
import re
import time
from collections import Counter, OrderedDict, defaultdict
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
from .merchandise import (kind as merchandise_kind, identity, COMPLEMENTS, DURABLE_KINDS,
                          is_complement, purchase_context, exclude_owned, unique_models,
                          is_gender_incompatible)


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
    1: [2, 9, 8, 1],       # Thiết Bị Điện Tử & Công Nghệ -> Âm Thanh, Điện Thoại, Đồng Hồ
    2: [1, 9, 8, 2],       # Âm Thanh & Phụ Kiện Máy Tính -> Điện Tử, Điện Thoại, Đồng Hồ
    3: [5, 8, 11, 3],      # Thời Trang Nam -> Giày Dép, Đồng Hồ, Thể Thao
    4: [7, 5, 8, 4],       # Thời Trang Nữ -> Mỹ Phẩm, Giày Dép Nữ, Đồng Hồ/Trang Sức
    5: [5, 3, 4, 11, 8],   # Giày Dép & Sneaker -> Phụ kiện giày (vớ/lót/vệ sinh), Thời Trang, Thể Thao
    6: [6, 10],            # Đồ Gia Dụng Thông Minh -> Đồ Bếp/Gia Dụng, Mẹ & Bé (KHÔNG CÓ CÔNG NGHỆ/ĐỒNG HỒ)
    7: [7, 4],             # Mỹ Phẩm & Sắc Đẹp -> Skincare cùng bộ (Tẩy trang -> Sữa rửa mặt, Serum, Kem dưỡng, Chống nắng), Thời Trang Nữ (TUYỆT ĐỐI KHÔNG CÔNG NGHỆ/ĐỒNG HỒ)
    8: [3, 4, 8],          # Đồng Hồ & Trang Sức -> Thời Trang Nam/Nữ
    9: [2, 8, 1, 9],       # Điện Thoại & Máy Tính Bảng -> Âm Thanh/Tai Nghe, Đồng Hồ, Điện Tử
    10: [10, 6, 7],        # Đồ Chơi & Mẹ Bé -> Sữa/Bình sữa/Tã bỉm, Gia Dụng, Chăm sóc em bé
    11: [11, 5, 3, 4],     # Thể Thao & Dã Ngoại -> Phụ kiện thể thao (túi vợt, cầu lông, bình nước, thảm yoga), Giày Thể Thao, Quần Áo Thể Thao (TUYỆT ĐỐI KHÔNG CÔNG NGHỆ/CHUỘT/ĐỒNG HỒ)
}

CATEGORY_COMPLEMENTS = {
    1: ('tai nghe', 'bàn phím', 'chuột', 'màn hình', 'củ sạc', 'cáp sạc', 'pin dự phòng', 'balo', 'lót chuột'),
    2: ('củ sạc', 'cáp sạc', 'pin dự phòng', 'giá đỡ', 'laptop', 'điện thoại'),
    3: ('đồng hồ', 'ví da', 'thắt lưng', 'kính', 'giày', 'tất', 'vớ', 'sneaker'),
    4: ('túi xách', 'son', 'serum', 'kem', 'kính', 'giày cao gót', 'sandal'),
    5: ('vớ', 'tất', 'lót giày', 'dây giày', 'vệ sinh giày', 'khử mùi', 'bình nước', 'thể thao'),
    6: ('chảo', 'hộp cơm', 'máy xay', 'bình giữ nhiệt', 'bàn ủi', 'khăn lau', 'giấy nến', 'dao'),
    7: ('sữa rửa mặt', 'nước tẩy trang', 'kem chống nắng', 'serum', 'kem dưỡng', 'son', 'bông tẩy trang', 'mặt nạ'),
    8: ('hộp đựng', 'khăn lau', 'dây da', 'ví da', 'vòng tay', 'dây chuyền'),
    9: ('tai nghe', 'củ sạc', 'cáp sạc', 'pin dự phòng', 'sạc', 'ốp', 'bao da', 'kính cường lực'),
    10: ('khăn ướt', 'bình sữa', 'sữa bột', 'tã', 'đồ chơi', 'ăn dặm'),
    11: ('bao vợt', 'vợt', 'cầu lông', 'thảm tập', 'con lăn', 'dây kháng lực', 'bình nước', 'túi thể thao', 'giày thể thao'),
}


def core_product_title(name: str) -> str:
    return identity({'name': name})


def build_shopee_feed(ranked, signals, limit=24, retail=False, user=None):
    """Build a balanced, harmonious Shopee/Taobao style feed:
    - High-intent items (sub-kind or category matching active user signals): ~60% of feed for active users
    - Complementary cross-category items: ~20% of feed
    - Diverse lifestyle & popular discovery: ~20% of feed across relevant demographic categories
    - Strict gender integrity: never leak women's dresses/makeup/heels to men or vice versa
    - Deduplication strictly by core product name (no photo filtering restriction)
    """
    if not ranked:
        return [], []

    # 1. Deduplicate candidates by product name & core title, filter out gender-incompatible items
    unique_candidates = []
    seen_names = set()
    seen_cores = set()
    for product, score in ranked:
        if is_gender_incompatible(product, user, signals):
            continue
        name = product['name'].strip().casefold()
        core = core_product_title(product['name'])
        if name in seen_names or (core and core in seen_cores):
            continue
        seen_names.add(name)
        if core:
            seen_cores.add(core)
        jitter = 0 if retail else random.uniform(-0.04, 0.04)
        unique_candidates.append((product, score + jitter))

    # 2. Extract recent customer intent across all active categories and handle durable purchase fatigue
    strengths = {}
    names = {}
    kind_strengths = {}
    purchased_kinds = set()
    purchased_ids = set()

    for index, row in enumerate(signals or []):
        cat = row['category_id']
        weight = ACTION_WEIGHTS.get(row['action_type'], 1.0) * (0.86**index)
        names[cat] = row.get('category_name') or f"Danh mục {cat}"
        p_name = row.get('product_name') or ''
        k = merchandise_kind({'name': p_name})
        if row.get('action_type') == 'purchase':
            if row.get('product_id'):
                purchased_ids.add(row['product_id'])
            if k in DURABLE_KINDS:
                purchased_kinds.add(k)
                # Transfer purchase weight to its complementary accessories
                for comp_k in COMPLEMENTS.get(k, set()):
                    kind_strengths[comp_k] = kind_strengths.get(comp_k, 0) + weight
                continue
        strengths[cat] = strengths.get(cat, 0) + weight
        if k:
            kind_strengths[k] = kind_strengths.get(k, 0) + weight

    # Multi-category intent recognition (all categories with meaningful interaction weight)
    intent_cats = {c for c, w in strengths.items() if w >= 0.7}
    intent_kinds = {k for k, w in kind_strengths.items() if w >= 0.7}
    comp_cats = set()
    for ic in intent_cats:
        comp_cats.update(COMPLEMENTARY_MAP.get(ic, []))
    comp_cats -= intent_cats

    # 3. Partition candidates into 3 distinct pools
    intent_pool = []
    comp_pool = []
    explore_pool = []

    for product, score in unique_candidates:
        if product.get('id') in purchased_ids:
            continue
        if is_gender_incompatible(product, user, signals):
            continue
        cid = product['category_id']
        p_kind = merchandise_kind(product)

        # Fatigue suppression: if user bought this durable kind, avoid flooding feed with more
        if p_kind in purchased_kinds:
            continue

        if intent_kinds and p_kind in intent_kinds:
            product['recommendation_reason'] = f"Gợi ý theo sở thích về {p_kind.title()}"
            intent_pool.append((product, score))
        elif intent_cats and cid in intent_cats:
            product['recommendation_reason'] = f"Hợp với hoạt động gần đây về {names.get(cid, '')}"
            intent_pool.append((product, score))
        elif (any(is_complement(product, {'name': s['product_name'], 'price': s.get('product_price', 10000000)})
                  for s in signals[:8] if s.get('product_name')) or cid in comp_cats or p_kind in kind_strengths):
            product['recommendation_reason'] = "Phụ kiện & gợi ý phối hợp phù hợp"
            comp_pool.append((product, score))
        else:
            product['recommendation_reason'] = "Gợi ý thịnh hành hôm nay"
            explore_pool.append((product, score))

    intent_pool.sort(key=lambda x: x[1], reverse=True)
    comp_pool.sort(key=lambda x: x[1], reverse=True)
    explore_pool.sort(key=lambda x: x[1], reverse=True)

    # Interleave explore_pool across categories to guarantee varied, non-monolithic shelves
    explore_by_cat = defaultdict(list)
    for it in explore_pool:
        explore_by_cat[it[0]['category_id']].append(it)
    rotated_explore = []
    cat_keys = list(explore_by_cat.keys())
    random.shuffle(cat_keys)
    max_len = max((len(v) for v in explore_by_cat.values()), default=0)
    for round_i in range(max_len):
        for ck in cat_keys:
            if round_i < len(explore_by_cat[ck]):
                rotated_explore.append(explore_by_cat[ck][round_i])
    explore_pool = rotated_explore

    # 4. Adaptive Quotas: High-intent gets priority when user has strong engagement history
    has_strong_signals = len(signals or []) >= 4 and bool(intent_cats or intent_kinds)
    if has_strong_signals:
        intent_target = min(15, len(intent_pool))
        comp_target = min(5, len(comp_pool))
        schedule = [
            'I', 'I', 'C', 'I', 'E',
            'I', 'I', 'C', 'I', 'E',
            'I', 'I', 'C', 'I', 'E',
            'I', 'I', 'C', 'I', 'E',
            'I', 'I', 'C', 'I', 'E'
        ]
    else:
        intent_target = min(5, len(intent_pool)) if intent_cats else 0
        comp_target = min(3, len(comp_pool)) if comp_cats else 0
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
            cur_idx = explore_idx
            found = False
            while cur_idx < len(explore_pool):
                cand = explore_pool[cur_idx][0]
                if is_gender_incompatible(cand, user, signals):
                    cur_idx += 1
                    continue
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
                    if is_gender_incompatible(cand, user, signals):
                        continue
                    c_name = cand['name'].strip().casefold()
                    c_core = core_product_title(cand['name'])
                    if c_name not in feed_names and (not c_core or c_core not in feed_cores):
                        chosen = cand
                        explore_cat_count[cand['category_id']] += 1
                        break

        if not chosen:
            for p, _ in unique_candidates:
                if is_gender_incompatible(p, user, signals):
                    continue
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
            if is_gender_incompatible(p, user, signals):
                continue
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

    def multicriteria_rank(self, products, user=None, target=None, touchpoint='home', cart=None,
                           signals=None, ai_scores=None, user_price=None, limit=24):
        scored = []
        u_gender = user.get('gender') if user else None
        u_prov = user.get('province_id') if user else None
        u_tier = user.get('member_tier') if user else None

        target_price = target['price'] if target else 500000
        target_cid = target['category_id'] if target else None
        target_kind = product_kind(target['name']) if target else None
        target_tokens = set(re.findall(r'\w+', target['name'].lower())) if target else set()

        comp_cats = set(COMPLEMENTARY_MAP.get(target_cid, [target_cid])) if target_cid else set()
        cart_cids = {i['category_id'] for i in (cart or []) if i.get('category_id')}
        cart_shops = {i['shop_name'] for i in (cart or []) if i.get('shop_name')}
        for cc in list(cart_cids):
            comp_cats.update(COMPLEMENTARY_MAP.get(cc, []))

        intent_cats = Counter()
        intent_kinds = Counter()
        for idx, s in enumerate(signals or []):
            w = {'purchase': 5.0, 'add_to_cart': 4.0, 'favorite': 3.0, 'click': 1.5, 'demo_interest': 3.5}.get(s.get('action_type'), 1.0) * (0.86**idx)
            if s.get('category_id'): intent_cats[s['category_id']] += w
            k = product_kind(s.get('product_name') or '')
            if k: intent_kinds[k] += w

        max_intent_cat = max(intent_cats.values(), default=1.0)
        max_intent_kind = max(intent_kinds.values(), default=1.0)

        # Dynamic range normalization for authentic MUSE model predictions
        min_ai = min(ai_scores.values()) if ai_scores else 0.0
        max_ai = max(ai_scores.values()) if ai_scores else 1.0
        ai_span = max(1e-6, max_ai - min_ai)

        for p in products:
            raw_id = p.get('raw_item_id')
            price = max(1, p.get('price', 0))
            cid = p.get('category_id')
            p_kind = product_kind(p.get('name', ''))

            # 1. AI Model Score (0.35)
            s_ai = 0.40
            if ai_scores and raw_id in ai_scores:
                s_ai = (ai_scores[raw_id] - min_ai) / ai_span
            else:
                s_ai = min(1.0, math.log(1 + p.get('sold_count', 0)) / 10.0) * 0.40

            # 2. Context & Intent Relevance (0.25)
            s_ctx = 0.30
            reason = 'Gợi ý phù hợp dành cho bạn'

            if touchpoint == 'similar' and target:
                if cid == target_cid: s_ctx += 0.25
                if target_kind and p_kind == target_kind:
                    s_ctx += 0.35
                    reason = f'Cùng dòng {target_kind.title()} · Giá tương đương'
                else:
                    reason = 'Cùng danh mục · Mẫu bán chạy'
                price_ratio = abs(math.log(price / target_price))
                s_ctx += max(0.0, 0.20 * math.exp(-0.5 * (price_ratio / 0.69)**2))
                p_tokens = set(re.findall(r'\w+', p['name'].lower()))
                overlap = len(target_tokens & p_tokens) / max(1, len(target_tokens))
                s_ctx += min(0.20, overlap * 0.40)

            elif touchpoint == 'complementary' and target:
                if target_cid == 7:  # Mỹ Phẩm & Sắc Đẹp
                    if cid == 7:
                        if p_kind in ('cleanser', 'serum', 'moisturizer', 'sunscreen', 'lipstick', 'makeup-remover'):
                            s_ctx += 0.55
                            reason = 'Bước dưỡng tiếp theo cho chu trình làm đẹp'
                        else:
                            s_ctx += 0.35
                            reason = f'Sản phẩm làm đẹp mua kèm cùng {target["name"][:20]}…'
                    elif cid == 4:
                        s_ctx += 0.25
                        reason = 'Thời trang & phụ kiện làm đẹp phù hợp'
                    else:
                        s_ctx -= 0.70  # Strictly reject tech/cookware/watches when viewing cosmetics
                elif target_cid == 11:  # Thể Thao & Dã Ngoại
                    if cid == 11:
                        s_ctx += 0.55
                        reason = 'Phụ kiện thể thao bổ trợ hoàn hảo'
                    elif cid in (5, 3, 4):
                        s_ctx += 0.35
                        reason = 'Trang bị thể thao & dã ngoại phù hợp'
                    else:
                        s_ctx -= 0.70  # Strictly reject tech/mice when viewing sports
                elif target_cid == 5:  # Giày dép
                    if cid == 5 and p_kind in ('socks', 'shoe-insole', 'shoe-cleaner', 'shoelaces', 'shoe-deodorizer'):
                        s_ctx += 0.55
                        reason = 'Phụ kiện chăm sóc & vớ mua kèm'
                    elif cid in (3, 4, 11):
                        s_ctx += 0.35
                        reason = 'Trang phục & thể thao phối cùng giày'
                    elif p_kind == 'shoes':
                        s_ctx -= 0.35  # Fatigue
                else:
                    if cid in comp_cats and cid != target_cid:
                        s_ctx += 0.35
                        reason = f'Phụ kiện hoàn hảo cho {target["name"][:25]}…'
                    elif cid in comp_cats:
                        s_ctx += 0.20
                        reason = f'Mua kèm tiện lợi cùng {target["name"][:25]}…'
                if 0.05 * target_price <= price <= 1.2 * target_price:
                    s_ctx += 0.15

            elif touchpoint in ('orders', 'post_purchase'):
                if target:
                    if target_cid == 11:
                        if cid == 11:
                            s_ctx += 0.55
                            reason = 'Phụ kiện thể thao mua kèm đơn hàng'
                        elif cid in (5, 3, 4):
                            s_ctx += 0.35
                            reason = 'Trang bị thể thao & dã ngoại mua kèm'
                        else:
                            s_ctx -= 0.70
                    elif target_cid == 7:
                        if cid == 7:
                            s_ctx += 0.55
                            reason = 'Sản phẩm chăm sóc da mua kèm đơn hàng'
                        elif cid == 4:
                            s_ctx += 0.30
                            reason = 'Thời trang & làm đẹp mua kèm đơn hàng'
                        else:
                            s_ctx -= 0.70
                    elif target_cid == 5:
                        if cid == 5 and p_kind in ('socks', 'shoe-insole', 'shoe-cleaner', 'shoelaces', 'shoe-deodorizer'):
                            s_ctx += 0.55
                            reason = 'Phụ kiện chăm sóc & vớ mua kèm đơn hàng'
                        elif cid in (3, 4, 11):
                            s_ctx += 0.35
                            reason = 'Trang phục thể thao mua kèm đơn hàng'
                        elif p_kind == 'shoes':
                            s_ctx -= 0.40
                    elif cid in comp_cats:
                        s_ctx += 0.35
                        reason = 'Mua kèm tiện lợi cho đơn hàng'
                    else:
                        s_ctx += 0.15
                        reason = 'Gợi ý thêm cho đơn hàng của bạn'
                else:
                    s_ctx += 0.20
                    reason = 'Gợi ý mua kèm đơn hàng vừa đặt'

            elif touchpoint == 'cart':
                if cart and p.get('shop_name') in cart_shops:
                    s_ctx += 0.30
                    reason = f'Cùng shop {p.get("shop_name", "")} · Gom đơn Freeship'
                elif cart and cid in comp_cats:
                    s_ctx += 0.25
                    reason = 'Phụ kiện bổ trợ cho sản phẩm trong giỏ'
                elif intent_cats and cid in intent_cats:
                    s_ctx += 0.25 * (intent_cats[cid] / max_intent_cat)
                    reason = 'Sản phẩm theo sở thích quan tâm gần đây'
                else:
                    s_ctx += 0.15
                    reason = 'Sản phẩm giá tốt mua kèm giỏ hàng'
                if price <= 350000: s_ctx += 0.15

            elif touchpoint == 'home':
                if intent_kinds and p_kind in intent_kinds:
                    s_ctx += 0.35 * (intent_kinds[p_kind] / max_intent_kind)
                    reason = f'Gợi ý theo sở thích {p_kind.title()}'
                elif intent_cats and cid in intent_cats:
                    s_ctx += 0.25 * (intent_cats[cid] / max_intent_cat)
                    reason = 'Hợp với hoạt động quan tâm gần đây'
                else:
                    s_ctx += 0.15
                    reason = 'Gợi ý thịnh hành hôm nay'

            # 3. User Demographics & Spending Tier (0.20)
            s_user = 0.50
            if u_gender == 'Nam':
                if cid == 3: s_user += 0.30  # Men fashion
                elif cid in (1, 2, 5, 8, 11): s_user += 0.15
                elif cid == 4: s_user -= 0.60  # Avoid dresses/skirts for men
                elif cid == 7 and p_kind in ('lipstick', 'skirt', 'dress'): s_user -= 0.60
            elif u_gender == 'Nữ':
                if cid in (4, 7): s_user += 0.30  # Women fashion & beauty
                elif cid in (5, 8, 10, 6): s_user += 0.15
                elif cid == 3: s_user -= 0.60  # Avoid men clothing for women
            if user and 'Gia Đình' in user.get('full_name', ''):
                if cid in (10, 6): s_user += 0.35  # Family baby & home goods
                elif cid == 11: s_user += 0.15

            if user_price and user_price.get('tier') != 'all':
                if user_price['min_price'] <= price <= user_price['max_price']:
                    s_user += 0.18

            if u_prov and p.get('province_id') == u_prov:
                s_user += 0.15

            if u_tier in ('Kim Cương', 'Vàng') and p.get('is_mall'):
                s_user += 0.10

            # 4. Product Quality & Proof (0.10)
            star = max(0.0, (p.get('rating_star', 4.5) - 3.0) / 2.0)
            sold = min(1.0, math.log(1 + p.get('sold_count', 0)) / 10.0)
            disc = min(1.0, p.get('discount_percent', 0) / 50.0)
            s_qual = 0.40 * star + 0.35 * sold + 0.25 * disc

            # 5. Merchant & Logistics (0.10)
            s_merch = (0.12 if p.get('is_mall') else 0.0) + (0.08 if p.get('is_freeship') else 0.0)

            jitter = random.uniform(-0.02, 0.02)

            final_score = 0.35 * s_ai + 0.25 * s_ctx + 0.20 * s_user + 0.10 * s_qual + 0.10 * s_merch + jitter
            p['recommendation_reason'] = reason
            p['ranking_score'] = round(final_score, 5)
            scored.append((p, final_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored]

    def recommend(self, user_id=None, touchpoint='home', product_id=None, limit=24, category_id=None,
                  display_category='', presentation_policy='original', focus_product_id=None, *,
                  write_logs=True, order_id=None):
        from app.recommender.commerce import user_price_affinity
        start = time.perf_counter()
        with connection() as db:
            user = dict(db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()) if user_id else {}
            u_price = user_price_affinity(db, user_id) if user_id else None
            effective_product_id = product_id or focus_product_id
            target = dict(db.execute('''SELECT p.*, pr.name province_name FROM products p
                LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.id=?''', (effective_product_id,)).fetchone()) if effective_product_id else None
            cart = cart_rows(db, user_id) if user_id else []
            signals = [dict(r) for r in db.execute('''SELECT h.action_type, p.category_id, c.name category_name, p.id product_id, p.name product_name, p.price product_price
                FROM user_behavior_history h JOIN products p ON p.id=h.product_id
                JOIN categories c ON c.id=p.category_id
                WHERE h.user_id=? AND h.action_type IN ('demo_interest','click','add_to_cart','purchase','favorite')
                ORDER BY h.id DESC LIMIT 24''', (user_id,))] if user_id else []

            # 1. Broad Multi-Channel Candidate Retrieval
            products = []
            seen_p = {target['id']} if target else set()

            if touchpoint == 'similar':
                if not target:
                    raise HTTPException(404, 'Sản phẩm không tồn tại.')
                cid = target['category_id']
                # Same category candidates (up to 120)
                for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                    LEFT JOIN provinces pr ON pr.id=p.province_id
                    WHERE p.category_id=? AND p.stock>0 AND p.id!=?
                    ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 120''', (cid, target['id'])):
                    d = dict(r)
                    if d['id'] not in seen_p:
                        seen_p.add(d['id'])
                        products.append(d)
                # Complementary categories for diversity (up to 60)
                for cc in COMPLEMENTARY_MAP.get(cid, [cid])[:3]:
                    if cc == cid: continue
                    for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id
                        WHERE p.category_id=? AND p.stock>0 AND p.id!=?
                        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 25''', (cc, target['id'])):
                        d = dict(r)
                        if d['id'] not in seen_p:
                            seen_p.add(d['id'])
                            products.append(d)

            elif touchpoint == 'complementary':
                if not target:
                    raise HTTPException(404, 'Sản phẩm không tồn tại.')
                cid = target['category_id']
                ordered_cids = COMPLEMENTARY_MAP.get(cid, [cid])
                # If target is cosmetics (7), prioritize specific skincare complements:
                if cid == 7:
                    for kw in ('sữa rửa mặt', 'kem chống nắng', 'serum', 'kem dưỡng', 'son', 'bông tẩy trang'):
                        for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id
                            WHERE p.category_id=7 AND p.name LIKE ? AND p.stock>0 AND p.id!=?
                            ORDER BY p.rating_star DESC, p.sold_count DESC LIMIT 20''', (f'%{kw}%', target['id'])):
                            d = dict(r)
                            if d['id'] not in seen_p:
                                seen_p.add(d['id'])
                                products.append(d)
                # If target is sports (11), prioritize sports accessories:
                elif cid == 11:
                    for kw in ('bao vợt', 'vợt', 'cầu lông', 'thảm tập', 'dây kháng lực', 'bình nước', 'túi thể thao'):
                        for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id
                            WHERE p.category_id=11 AND p.name LIKE ? AND p.stock>0 AND p.id!=?
                            ORDER BY p.rating_star DESC, p.sold_count DESC LIMIT 20''', (f'%{kw}%', target['id'])):
                            d = dict(r)
                            if d['id'] not in seen_p:
                                seen_p.add(d['id'])
                                products.append(d)
                # If target is shoes (5), prioritize shoe care & socks:
                elif cid == 5:
                    for kw in ('vớ', 'tất', 'lót giày', 'dây giày', 'vệ sinh', 'khử mùi', 'bình nước'):
                        for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id
                            WHERE p.name LIKE ? AND p.stock>0 AND p.id!=?
                            ORDER BY p.rating_star DESC, p.sold_count DESC LIMIT 20''', (f'%{kw}%', target['id'])):
                            d = dict(r)
                            if d['id'] not in seen_p:
                                seen_p.add(d['id'])
                                products.append(d)
                # Query allowed complementary categories:
                for cc in ordered_cids[:4]:
                    for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id
                        WHERE p.category_id=? AND p.stock>0 AND p.id!=?
                        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 40''', (cc, target['id'])):
                        d = dict(r)
                        if d['id'] not in seen_p:
                            seen_p.add(d['id'])
                            products.append(d)

            elif touchpoint == 'cart':
                cart_cids = list(dict.fromkeys(i['category_id'] for i in cart if i.get('category_id')))
                cart_shops = list({i['shop_name'] for i in cart if i.get('shop_name')})
                comp_cids = []
                for cc in cart_cids:
                    for c in COMPLEMENTARY_MAP.get(cc, [cc]):
                        if c not in comp_cids: comp_cids.append(c)
                if not comp_cids:
                    comp_cids = list(range(1, 12))
                for cc in comp_cids[:6]:
                    for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id
                        WHERE p.category_id=? AND p.stock>0
                        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 35''', (cc,)):
                        d = dict(r)
                        if d['id'] not in seen_p:
                            seen_p.add(d['id'])
                            products.append(d)
                if cart_shops:
                    placeholders = ','.join('?' for _ in cart_shops[:4])
                    for r in db.execute(f'''SELECT p.*, pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id
                        WHERE p.shop_name IN ({placeholders}) AND p.stock>0
                        ORDER BY p.rating_star DESC, p.sold_count DESC LIMIT 30''', cart_shops[:4]):
                        d = dict(r)
                        if d['id'] not in seen_p:
                            seen_p.add(d['id'])
                            products.append(d)

            elif touchpoint in ('orders', 'post_purchase'):
                order_products = []
                if order_id:
                    order_rows = db.execute('''SELECT p.*, pr.name province_name FROM order_items oi
                        JOIN products p ON p.id=oi.product_id
                        LEFT JOIN provinces pr ON pr.id=p.province_id
                        WHERE oi.order_id=?''', (order_id,)).fetchall()
                    order_products = [dict(r) for r in order_rows]
                if not order_products and target:
                    order_products = [target]
                order_pids = {p['id'] for p in order_products}
                order_cids = list(dict.fromkeys(p['category_id'] for p in order_products if p.get('category_id')))
                if not target and order_products:
                    target = order_products[0]

                comp_cids = []
                for occ in order_cids:
                    for cc in COMPLEMENTARY_MAP.get(occ, []):
                        if cc not in comp_cids: comp_cids.append(cc)
                if not comp_cids:
                    comp_cids = [11, 5, 3, 4] if 11 in order_cids else [1, 2, 9]

                # Specific complements for ordered product categories:
                if 11 in order_cids:
                    for kw in ('bao vợt', 'vợt', 'cầu lông', 'thảm tập', 'dây kháng lực', 'bình nước', 'túi thể thao', 'giày thể thao'):
                        for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id
                            WHERE p.category_id=11 AND p.name LIKE ? AND p.stock>0
                            ORDER BY p.rating_star DESC, p.sold_count DESC LIMIT 20''', (f'%{kw}%',)):
                            d = dict(r)
                            if d['id'] not in seen_p and d['id'] not in order_pids:
                                seen_p.add(d['id'])
                                products.append(d)
                elif 7 in order_cids:
                    for kw in ('sữa rửa mặt', 'kem chống nắng', 'serum', 'kem dưỡng', 'son', 'bông tẩy trang'):
                        for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id
                            WHERE p.category_id=7 AND p.name LIKE ? AND p.stock>0
                            ORDER BY p.rating_star DESC, p.sold_count DESC LIMIT 20''', (f'%{kw}%',)):
                            d = dict(r)
                            if d['id'] not in seen_p and d['id'] not in order_pids:
                                seen_p.add(d['id'])
                                products.append(d)
                elif 5 in order_cids:
                    for kw in ('vớ', 'tất', 'lót giày', 'dây giày', 'vệ sinh', 'khử mùi', 'bình nước'):
                        for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id
                            WHERE p.category_id=5 AND p.name LIKE ? AND p.stock>0
                            ORDER BY p.rating_star DESC, p.sold_count DESC LIMIT 20''', (f'%{kw}%',)):
                            d = dict(r)
                            if d['id'] not in seen_p and d['id'] not in order_pids:
                                seen_p.add(d['id'])
                                products.append(d)

                for cc in comp_cids[:4]:
                    for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.stock>0
                        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 35''', (cc,)):
                        d = dict(r)
                        if d['id'] not in seen_p and d['id'] not in order_pids:
                            seen_p.add(d['id'])
                            products.append(d)

            else:  # 'home', 'deals', or category browsing
                if category_id is not None:
                    products = [dict(r) for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                        LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.stock>0
                        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 240''', (category_id,))]
                else:
                    # Multi-channel personalized recall
                    purchases = purchase_context(db, user_id) if user_id else {'keys': set(), 'recent_kinds': set(), 'items': []}
                    purchased_ids = {p['id'] for p in purchases['items']} | {s['product_id'] for s in signals if s.get('action_type') == 'purchase'}
                    purchased_kinds = purchases['recent_kinds'] | {merchandise_kind({'name': s.get('product_name', '')}) for s in signals if s.get('action_type') == 'purchase' and merchandise_kind({'name': s.get('product_name', '')}) in DURABLE_KINDS}

                    seen_p = set(purchased_ids)

                    # Channel 1: Intent & History Complements
                    for s in signals[:6]:
                        p_name = s.get('product_name') or ''
                        s_cid = s.get('category_id')
                        k = merchandise_kind({'name': p_name})
                        if s.get('action_type') == 'purchase' and k in DURABLE_KINDS:
                            # User bought durable item (e.g. shoes) -> query its accessories/complements!
                            comp_cids = COMPLEMENTARY_MAP.get(s_cid, [s_cid]) if s_cid else [11, 5, 3]
                            for cc in comp_cids[:3]:
                                for comp_k in list(COMPLEMENTS.get(k, set()))[:2]:
                                    for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                                        LEFT JOIN provinces pr ON pr.id=p.province_id
                                        WHERE p.category_id=? AND p.name LIKE ? AND p.stock>0
                                        ORDER BY p.rating_star DESC, p.sold_count DESC LIMIT 15''', (cc, f'%{comp_k}%')):
                                        d = dict(r)
                                        if d['id'] not in seen_p:
                                            seen_p.add(d['id'])
                                            products.append(d)
                        elif s_cid:
                            for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                                LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.stock>0
                                ORDER BY p.rating_star DESC, p.sold_count DESC LIMIT 25''', (s_cid,)):
                                d = dict(r)
                                if d['id'] not in seen_p:
                                    seen_p.add(d['id'])
                                    products.append(d)

                    # Channel 2: Demographic & Preference Alignment
                    u_gender = user.get('gender')
                    user_signal_cids = {s.get('category_id') for s in signals}
                    demo_cids = []
                    if u_gender == 'Nam':
                        demo_cids = [3, 5, 1, 9, 11, 8]
                    elif u_gender == 'Nữ':
                        demo_cids = [4, 7, 5, 8, 6]
                    if user and 'Gia Đình' in user.get('full_name', ''):
                        demo_cids = [10, 6, 11, 5]
                    for dc in demo_cids[:4]:
                        offset = ((user_id or 1) * 11 + dc * 5) % 40
                        for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.stock>0
                            ORDER BY p.sold_count DESC LIMIT 20 OFFSET ?''', (dc, offset)):
                            d = dict(r)
                            if d['id'] not in seen_p and not is_gender_incompatible(d, user, signals):
                                seen_p.add(d['id'])
                                products.append(d)

                    # Channel 3: Broad diverse lifestyle discovery across relevant demographic categories
                    cat_offset = ((user_id or 1) * 17 + random.randint(0, 20)) % 50
                    explore_cids = list(range(1, 12))
                    if u_gender == 'Nam':
                        if 4 not in user_signal_cids and 4 in explore_cids:
                            explore_cids.remove(4)
                        if 'Gia Đình' not in user.get('full_name', '') and 10 not in user_signal_cids and 10 in explore_cids:
                            explore_cids.remove(10)
                        if 7 not in user_signal_cids and 7 in explore_cids:
                            explore_cids.remove(7)
                    elif u_gender == 'Nữ':
                        if 3 not in user_signal_cids and 3 in explore_cids:
                            explore_cids.remove(3)

                    for cid in explore_cids:
                        for r in db.execute('''SELECT p.*, pr.name province_name FROM products p
                            LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.category_id=? AND p.stock>0
                            ORDER BY p.sold_count DESC LIMIT 15 OFFSET ?''', (cid, cat_offset)):
                            d = dict(r)
                            if d['id'] not in seen_p and not is_gender_incompatible(d, user, signals):
                                seen_p.add(d['id'])
                                products.append(d)

        metadata = {}
        model = self.model
        ai_scores = {}
        model_used = False
        strategy = 'MUSE Multi-Criteria (AI + Context + Demographics + Quality + Merchant)'
        engine = 'Catalog Multi-Criteria Ranking'
        metric = 'ranking_score'
        inference_start = time.perf_counter()

        if model and products:
            try:
                model.items.register_products(products + ([target] if target else []))
                mapped = [p for p in products if p['raw_item_id'] in model.items]
                valid_raw = [p['raw_item_id'] for p in mapped]
                if touchpoint in ('similar', 'complementary') and target and target.get('raw_item_id') in model.items:
                    if valid_raw:
                        sims = model.similarities(target['raw_item_id'], valid_raw)
                        ai_scores = dict(zip(valid_raw, sims))
                        model_used = True
                        engine = 'MUSE SCL 128D Embedding'
                        metric = 'cosine_similarity'
                        for p in mapped:
                            if p['raw_item_id'] in ai_scores:
                                p['similarity'] = round(ai_scores[p['raw_item_id']], 6)
                elif user_id and valid_raw:
                    preds, extra = model.predict(user_id, valid_raw[:220])
                    ai_scores = dict(zip(valid_raw[:220], preds))
                    metadata.update(extra)
                    model_used = True
                    engine = 'Alibaba MUSE DIN + GSU'
                    metric = 'p_click'
                    for p in mapped:
                        if p['raw_item_id'] in ai_scores:
                            p['p_click'] = round(ai_scores[p['raw_item_id']], 7)
            except Exception as exc:
                logging.exception('AI scoring failed; continuing with full multi-criteria ranking: %s', exc)

        inference_ms = (time.perf_counter() - inference_start) * 1000

        # Multi-Criteria Scoring & Ranking
        scored_products = self.multicriteria_rank(
            products,
            user=user,
            target=target,
            touchpoint=touchpoint,
            cart=cart,
            signals=signals,
            ai_scores=ai_scores,
            user_price=u_price
        )

        for p in scored_products:
            p['recommendation_source'] = 'ai' if model_used else 'catalog'

        intent_summary = []
        if touchpoint == 'home':
            ranked_tuples = [(p, p.get('ranking_score', 0.5)) for p in scored_products]
            top, intent_summary = build_shopee_feed(ranked_tuples, signals, limit=limit, user=user)
        else:
            top = []
            seen_names = set()
            seen_cores = set()
            for p in scored_products:
                if is_gender_incompatible(p, user, signals):
                    continue
                name = p['name'].strip().casefold()
                core = core_product_title(p['name'])
                if name in seen_names or (core and core in seen_cores):
                    continue
                seen_names.add(name)
                if core: seen_cores.add(core)
                item = public_product(p)
                item['recommendation_reason'] = p.get('recommendation_reason', 'Gợi ý phù hợp dành cho bạn')
                item['recommendation_source'] = p.get('recommendation_source', 'catalog')
                if 'ranking_score' in p: item['ranking_score'] = p['ranking_score']
                if 'p_click' in p: item['p_click'] = p['p_click']
                if 'similarity' in p: item['similarity'] = p['similarity']
                top.append(item)
                if len(top) >= limit:
                    break

        active_interest = next(({'category_id': row['category_id'], 'category_name': row['category_name'],
                                 'product_id': row['product_id']} for row in signals
                                if row['action_type'] == 'demo_interest'), None)

        metadata.update({
            'engine': engine, 'strategy': strategy, 'score_type': metric,
            'candidate_count': len(products), 'result_count': len(top),
            'inference_ms': round(inference_ms, 2), 'latency_ms': round((time.perf_counter() - start) * 1000, 2),
            'checkpoint_loaded': model is not None, 'model_used': model_used, 'touchpoint': touchpoint,
            'ranking_policy': 'multi_criteria_ranking_with_diversity',
            'has_more': len(products) > limit, 'active_interest': active_interest,
            'intent_summary': intent_summary
        })

        if user_id and write_logs:
            with self.metrics_lock:
                self.last_metrics[user_id] = metadata
                self.last_metrics.move_to_end(user_id)
                while len(self.last_metrics) > 128:
                    self.last_metrics.popitem(last=False)
            with connection(write=True) as db:
                db.execute('''INSERT INTO recommendation_logs(user_id,touchpoint,candidate_count,top_recommended_ids,model_name,latency_ms)
                    VALUES (?,?,?,?,?,?)''', (user_id, touchpoint, len(products), ','.join(str(x['id']) for x in top), engine, metadata['latency_ms']))

        quality = evaluation_summary() if model_used and metric == 'p_click' else {'available': False, 'reason': 'not_click_ranking'}
        return {'items': top, 'meta': metadata, 'quality': quality}


service=RecommendationService()
