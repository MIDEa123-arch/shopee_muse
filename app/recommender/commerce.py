"""Visible merchandise constraints, separate from model inputs and score math."""
import json
import random
import re
from collections import Counter

from fastapi import HTTPException

from app import config
from app.storefront import CATEGORIES, TYPE_LABELS, presentation_map

COMPLEMENTARY_TYPE_MAP = {
    # Electronics & Gadgets
    'smartphones': ['phone-cases', 'charging', 'headphones'],
    'laptops': ['headphones', 'charging', 'speakers', 'camera-accessories'],
    'tablets': ['charging', 'headphones', 'speakers'],
    'headphones': ['charging', 'speakers'],
    'speakers': ['charging', 'headphones'],
    'charging': ['smartphones', 'tablets', 'headphones'],
    'phone-cases': ['smartphones', 'charging', 'headphones'],
    'camera-accessories': ['smartphones', 'laptops', 'charging', 'headphones'],
    # Sports & Outdoor
    'sports-accessories': ['sports-accessories', 'mens-shoes', 'mens-shirts', 'headphones'],
    # Home & Kitchen
    'cookware': ['kitchen-accessories', 'kitchen-appliances', 'home-decoration'],
    'kitchen-appliances': ['cookware', 'kitchen-accessories', 'home-decoration'],
    'kitchen-accessories': ['cookware', 'kitchen-appliances', 'home-decoration'],
    'furniture': ['home-decoration', 'kitchen-accessories', 'cookware'],
    'home-decoration': ['furniture', 'kitchen-accessories', 'cookware'],
    # Beauty & Personal Care
    'beauty': ['skin-care', 'fragrances', 'womens-jewellery'],
    'skin-care': ['beauty', 'fragrances', 'womens-bags'],
    'fragrances': ['beauty', 'skin-care', 'womens-jewellery', 'sunglasses'],
    # Men's Fashion
    'mens-shirts': ['mens-shoes', 'mens-watches', 'sunglasses', 'sports-accessories'],
    'mens-shoes': ['mens-shirts', 'mens-watches', 'sports-accessories', 'sunglasses'],
    'mens-watches': ['mens-shirts', 'sunglasses', 'mens-shoes'],
    # Women's Fashion
    'womens-clothing': ['womens-shoes', 'womens-bags', 'womens-jewellery', 'beauty'],
    'womens-shoes': ['womens-clothing', 'womens-bags', 'womens-jewellery', 'sunglasses'],
    'womens-bags': ['womens-shoes', 'womens-clothing', 'womens-jewellery', 'sunglasses'],
    'womens-jewellery': ['womens-clothing', 'womens-bags', 'beauty', 'fragrances'],
    'womens-watches': ['womens-clothing', 'womens-jewellery', 'womens-bags'],
    # Unisex & Accessories
    'sunglasses': ['mens-shirts', 'womens-clothing', 'watches', 'womens-bags'],
    'watches': ['mens-shirts', 'sunglasses', 'womens-clothing'],
}

CATEGORY_COMPLEMENTARY_FALLBACK = {
    'electronics': ['charging', 'headphones', 'smartphones', 'speakers'],
    'fashion': ['mens-shoes', 'womens-shoes', 'sunglasses', 'watches'],
    'home': ['kitchen-accessories', 'cookware', 'home-decoration', 'kitchen-appliances'],
    'beauty': ['skin-care', 'fragrances', 'beauty'],
    'watches': ['sunglasses', 'mens-shirts', 'womens-clothing'],
    'bags': ['sunglasses', 'womens-shoes', 'womens-clothing'],
    'shoes': ['mens-shirts', 'womens-clothing', 'sports-accessories'],
    'sports': ['sports-accessories', 'mens-shoes', 'headphones'],
}

FEMALE_ONLY_TYPES = {'womens-clothing', 'womens-shoes', 'womens-bags', 'womens-jewellery', 'beauty'}
MALE_ONLY_TYPES = {'mens-shirts', 'mens-shoes', 'mens-watches'}


def apply_gender_filter(displays, products, user_gender, display_category=None):
    if not user_gender or display_category:
        return products
    g = user_gender.strip().capitalize()
    if g == 'Nam':
        return [p for p in products if (d := displays.get(p['id'])) and d.get('presentation_type') not in FEMALE_ONLY_TYPES]
    elif g in ('Nữ', 'Nu'):
        return [p for p in products if (d := displays.get(p['id'])) and d.get('presentation_type') not in MALE_ONLY_TYPES]
    return products


def context_candidates(db, products, user_id, touchpoint, target, display_category, focus_product_id, mode):
    displays = presentation_map(str(config.DB_PATH))
    if not displays:
        return None, set(), {'enabled': False, 'reason': 'no_presentation'}
    setting = db.execute("SELECT value FROM catalog_settings WHERE key='storefront_context'").fetchone()
    boundary = json.loads(setting[0])['after_behavior_id'] if setting else db.execute('SELECT COALESCE(MAX(id),0) FROM user_behavior_history').fetchone()[0]
    recent = list(db.execute('''SELECT product_id,action_type FROM user_behavior_history WHERE user_id=? AND id>?
        AND action_type IN ('click','favorite','add_to_cart','purchase') ORDER BY id DESC LIMIT 1000''',
        (user_id, boundary))) if user_id else []
    recent_templates = {displays[r['product_id']]['template_id'] for r in recent if r['product_id'] in displays}
    focus = None; types = set(); excluded = set(); source = 'browse'; label = 'Tất cả sản phẩm'

    if touchpoint in ('similar', 'complementary'):
        focus = displays.get(target['id']) if target else None
        source = 'viewed_product' if touchpoint == 'similar' else 'purchased_product'
        if focus:
            base_type = focus['presentation_type']
            types.add(base_type)
            excluded.add(focus['template_id'])
    elif touchpoint == 'cart':
        cart = list(db.execute('SELECT product_id FROM cart_items WHERE user_id=?', (user_id,))) if user_id else []
        for row in cart:
            item = displays.get(row['product_id'])
            if item:
                types.add(item['presentation_type'])
                excluded.add(item['template_id'])
        source = 'cart'; label = 'Sản phẩm tương tự giỏ hàng'
    elif touchpoint == 'home':
        excluded = recent_templates
        if display_category:
            source = 'selected_category'
            label = next((c['name'] for c in CATEGORIES if c['slug'] == display_category), 'Danh mục đã chọn')
        elif mode == 'contextual':
            if focus_product_id is not None:
                focus = displays.get(focus_product_id)
                if not focus:
                    raise HTTPException(404, 'Sản phẩm làm ngữ cảnh không tồn tại.')
                source = 'selected_product'
            else:
                focus = next((displays[r['product_id']] for r in recent if r['product_id'] in displays), None)
                if focus: source = 'recent_web_action'
            if focus:
                base_type = focus['presentation_type']
                types.add(base_type)
                excluded.add(focus['template_id'])

    if types and len(types) == 1:
        label = TYPE_LABELS.get(next(iter(types)), 'Cùng loại sản phẩm')
    elif focus:
        label = f"Tiếp nối {focus['name']} & phụ kiện đi kèm"

    context = {
        'enabled': True, 'source': source, 'label': label,
        'types': sorted(t for t in types if t),
        'focus_name': focus['name'] if focus else None,
        'focus_type': focus['presentation_type'] if focus else None,
        'focus_product_id': focus_product_id if focus_product_id else (target['id'] if target else None),
        'deduplicate': 'illustrative_product', 'model_scores_unchanged': True,
        'scope_key': source + ':' + (','.join(sorted(types)) if types else display_category or 'all')
    }

    strict = bool(types or display_category)
    ids = {p['id'] for p in products if (d := displays.get(p['id']))
           and (not strict or not types or d['presentation_type'] in types)
           and d['template_id'] not in excluded}
    return ids, excluded, context


def distinct_illustrations(products):
    """Keep the highest ranked ID for each paired photo/title, without rescoring."""
    displays = presentation_map(str(config.DB_PATH))
    seen_templates = set()
    seen_names = set()
    result = []
    for product in products:
        item = displays.get(product['id'])
        template_id = item['template_id'] if item else product['id']
        name_key = (item['name'] if item else product['name']).strip().casefold()
        if template_id not in seen_templates and name_key not in seen_names:
            seen_templates.add(template_id)
            seen_names.add(name_key)
            result.append(product)
    return result


def user_price_affinity(db, user_id):
    if not user_id:
        return {'tier': 'all', 'label': 'Đa dạng khúc giá', 'min_price': 0, 'max_price': 1000000000, 'avg_price': None}

    rows = db.execute('''SELECT p.price FROM user_behavior_history h
        JOIN products p ON p.id = h.product_id
        WHERE h.user_id = ? AND h.action_type IN ('click','favorite','add_to_cart','purchase')
        ORDER BY h.id DESC LIMIT 100''', (user_id,)).fetchall()

    cart_rows = db.execute('''SELECT p.price FROM cart_items c
        JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ?''', (user_id,)).fetchall()

    prices = [r[0] for r in rows if r[0] is not None] + [r[0] for r in cart_rows if r[0] is not None]
    if not prices or len(prices) < 2:
        return {'tier': 'all', 'label': 'Đa dạng khúc giá', 'min_price': 0, 'max_price': 1000000000, 'avg_price': None}

    avg_price = sum(prices) / len(prices)
    if avg_price < 350000:
        tier = 'budget'
        label = 'Phù hợp ngân sách tiết kiệm (< 350k)'
        min_p = 0
        max_p = 500000
    elif avg_price <= 1800000:
        tier = 'mid'
        label = 'Khúc giá ưa chuộng (350k - 2tr)'
        min_p = 250000
        max_p = 2500000
    else:
        tier = 'premium'
        label = 'Phân khúc cao cấp (> 1.5tr)'
        min_p = 1200000
        max_p = 1000000000

    return {
        'tier': tier,
        'label': label,
        'min_price': min_p,
        'max_price': max_p,
        'avg_price': int(avg_price)
    }


def complementary_bundle(db, user_id=None, focus_product_id=None):
    from app.database import public_product
    from app.recommender.service import service, COMPLEMENTARY_MAP
    displays = presentation_map(str(config.DB_PATH))

    focus = None
    focus_source = 'direct' if focus_product_id else 'popular'
    if focus_product_id:
        row = db.execute('SELECT p.*, c.name category_name FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=?', (focus_product_id,)).fetchone()
        if row:
            focus = dict(row)

    if not focus and user_id:
        cart_row = db.execute('''SELECT p.*, c.name category_name FROM cart_items ci
            JOIN products p ON p.id=ci.product_id
            JOIN categories c ON c.id=p.category_id
            WHERE ci.user_id=? ORDER BY ci.id DESC LIMIT 1''', (user_id,)).fetchone()
        if cart_row:
            focus = dict(cart_row)
            focus_source = 'cart'

    if not focus and user_id:
        hist_row = db.execute('''SELECT p.*, c.name category_name FROM user_behavior_history h
            JOIN products p ON p.id=h.product_id
            JOIN categories c ON c.id=p.category_id
            WHERE h.user_id=? AND h.action_type IN ('click','favorite','add_to_cart','purchase')
            ORDER BY h.id DESC LIMIT 1''', (user_id,)).fetchone()
        if hist_row:
            focus = dict(hist_row)
            focus_source = 'history'

    if not focus and user_id:
        order_row = db.execute('''SELECT p.*, c.name category_name FROM order_items oi
            JOIN orders o ON o.id=oi.order_id
            JOIN products p ON p.id=oi.product_id
            JOIN categories c ON c.id=p.category_id
            WHERE o.user_id=? AND o.order_status!='Đã hủy'
            ORDER BY o.id DESC, oi.id DESC LIMIT 1''', (user_id,)).fetchone()
        if order_row:
            focus = dict(order_row)
            focus_source = 'order'

    if not focus and user_id:
        wish_row = db.execute('''SELECT p.*, c.name category_name FROM wishlist w
            JOIN products p ON p.id=w.product_id
            JOIN categories c ON c.id=p.category_id
            WHERE w.user_id=? ORDER BY w.rowid DESC LIMIT 1''', (user_id,)).fetchone()
        if wish_row:
            focus = dict(wish_row)
            focus_source = 'wishlist'

    if not focus:
        focus_row = db.execute('''SELECT p.*, c.name category_name FROM products p
            JOIN categories c ON c.id=p.category_id
            WHERE p.id <= 10000 AND p.stock>0
            ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 1''').fetchone()
        if focus_row:
            focus = dict(focus_row)
            focus_source = 'popular'

    if not focus:
        return {'focus': None, 'items': [], 'bundle_label': 'Gợi ý combo sản phẩm'}

    if not displays:
        # 2,000,000 Vietnamese catalog mode (tiki-vn): select complementary cross-sell bundle via MUSE
        focus_cat_id = focus['category_id']
        comp_cats = list(COMPLEMENTARY_MAP.get(focus_cat_id, [focus_cat_id]))
        # Prioritize cross-category accessories first before same-category add-ons
        ordered_cats = [c for c in comp_cats if c != focus_cat_id] + ([focus_cat_id] if focus_cat_id in comp_cats else [])
        focus_words = focus['name'].lower().split()[:2]
        focus_prefix = ' '.join(focus_words)

        raw_candidates = []
        seen_ids = {focus['id']}
        for cid in ordered_cats:
            rows = db.execute('''SELECT p.*, c.name category_name, pr.name province_name
                FROM products p
                JOIN categories c ON c.id=p.category_id
                LEFT JOIN provinces pr ON pr.id=p.province_id
                WHERE p.category_id=? AND p.id <= 50000 AND p.stock>0 AND p.id!=?
                ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 45''',
                (cid, focus['id'])).fetchall()
            for r in rows:
                d = dict(r)
                if d['id'] in seen_ids:
                    continue
                if d['name'].lower().startswith(focus_prefix):
                    continue
                seen_ids.add(d['id'])
                raw_candidates.append(d)

        model = service.model
        p_click_map = {}
        sim_map = {}
        if model and raw_candidates:
            try:
                model.items.register_products([focus] + raw_candidates)
                valid_raw = [c['raw_item_id'] for c in raw_candidates if c['raw_item_id'] in model.items]
                if valid_raw and focus['raw_item_id'] in model.items:
                    sims = model.similarities(focus['raw_item_id'], valid_raw)
                    sim_map = dict(zip(valid_raw, sims))
                if user_id and valid_raw:
                    scores, _ = model.predict(user_id, valid_raw)
                    p_click_map = dict(zip(valid_raw, scores))
            except Exception:
                pass

        def bundle_score(item):
            rid = item['raw_item_id']
            pc = p_click_map.get(rid, 0.0)
            sim = max(0.0, sim_map.get(rid, 0.0))
            cross_bonus = 0.08 if item['category_id'] != focus_cat_id else 0.0
            if user_id and p_click_map:
                return 0.65 * pc + 0.35 * sim + cross_bonus
            return sim + cross_bonus + (item.get('rating_star', 4.8) * 0.01)

        raw_candidates.sort(key=lambda c: (bundle_score(c), c.get('sold_count', 0)), reverse=True)

        focus_pub = public_product(focus)
        focus_short = ' '.join(focus['name'].split()[:4])
        selected_items = []
        seen_names = {focus['name'].strip().lower()}
        seen_photos = {focus_pub['image_url']}
        used_cats = Counter()

        # Pass 1: 1 best item per complementary category with distinct photo
        for cid in ordered_cats:
            for c in raw_candidates:
                if c['category_id'] != cid:
                    continue
                cname = c['name'].strip().lower()
                if cname in seen_names:
                    continue
                rid = c['raw_item_id']
                if rid in p_click_map:
                    c['p_click'] = round(p_click_map[rid], 6)
                if rid in sim_map:
                    c['similarity'] = round(sim_map[rid], 6)
                c['recommendation_source'] = 'ai' if (p_click_map or sim_map) else 'catalog'
                c['recommendation_reason'] = f"Mua kèm hoàn hảo với {focus_short}"
                pub = public_product(c)
                if pub['image_url'] in seen_photos:
                    continue
                selected_items.append(pub)
                seen_names.add(cname)
                seen_photos.add(pub['image_url'])
                used_cats[cid] += 1
                break
            if len(selected_items) >= 3:
                break

        # Pass 2: fill up to 3 items if needed
        if len(selected_items) < 3:
            for c in raw_candidates:
                cname = c['name'].strip().lower()
                if cname in seen_names:
                    continue
                rid = c['raw_item_id']
                if rid in p_click_map:
                    c['p_click'] = round(p_click_map[rid], 6)
                if rid in sim_map:
                    c['similarity'] = round(sim_map[rid], 6)
                c['recommendation_source'] = 'ai' if (p_click_map or sim_map) else 'catalog'
                c['recommendation_reason'] = f"Mua kèm hoàn hảo với {focus_short}"
                pub = public_product(c)
                if pub['image_url'] in seen_photos:
                    continue
                selected_items.append(pub)
                seen_names.add(cname)
                seen_photos.add(pub['image_url'])
                if len(selected_items) >= 3:
                    break

        if focus_source == 'cart':
            bundle_label = f"Combo mua kèm sản phẩm trong giỏ: {focus_short}"
        elif focus_source == 'order':
            bundle_label = f"Gợi ý phụ kiện đi kèm đơn hàng: {focus_short}"
        elif focus_source == 'wishlist':
            bundle_label = f"Combo phối kèm món bạn đã lưu: {focus_short}"
        elif focus_source == 'history':
            bundle_label = f"Thường được mua cùng món bạn vừa xem: {focus_short}"
        else:
            bundle_label = f"Thường được mua cùng nhau: {focus_short}"

        total_original = focus_pub['original_price'] + sum(p['original_price'] for p in selected_items)
        raw_sum = focus_pub['price'] + sum(p['price'] for p in selected_items)
        combo_price = int(raw_sum * 0.95)
        savings = max(total_original - combo_price, raw_sum - combo_price)
        discount_pct = round((savings / max(total_original, 1)) * 100) if total_original > 0 else 5

        return {
            'focus': focus_pub,
            'bundle_label': bundle_label,
            'focus_source': focus_source,
            'accessory_types': [str(c) for c in ordered_cats],
            'items': selected_items,
            'model_used': bool(p_click_map or sim_map),
            'pricing': {
                'original_total': total_original,
                'regular_total': raw_sum,
                'bundle_total': combo_price,
                'extra_combo_savings': raw_sum - combo_price,
                'savings': savings,
                'discount_percent': discount_pct
            }
        }

    focus_disp = displays.get(focus['id'])
    focus_type = focus_disp['presentation_type'] if focus_disp else 'smartphones'
    focus_cat = focus_disp['presentation_category'] if focus_disp else 'electronics'
    focus_name = focus_disp['name'] if focus_disp else focus['name']

    target_types = COMPLEMENTARY_TYPE_MAP.get(focus_type)
    if not target_types:
        target_types = CATEGORY_COMPLEMENTARY_FALLBACK.get(focus_cat, ['headphones', 'charging', 'smartphones'])

    candidates = [dict(r) for r in db.execute('''SELECT p.*, c.name category_name FROM products p
        JOIN categories c ON c.id=p.category_id
        WHERE p.id <= 15000 AND p.stock>0 AND p.id!=?
        ORDER BY p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 300''', (focus['id'],))]

    # Rank only inside a curated, context-safe accessory pool. Demographics never
    # hard-exclude merchandise because customers often shop for somebody else.
    score_map = {}
    model = service.model
    if user_id and model and candidates:
        try:
            from app.recommender.native import native_ranking
            model.items.register_products(candidates)
            eligible = [c for c in candidates if c['raw_item_id'] in model.items]
            score_map, _ = native_ranking.scores(model, user_id, eligible)
        except Exception:
            score_map = {}
    candidates.sort(key=lambda c: (-score_map.get(c['raw_item_id'], -1.0),
                                   -(c.get('rating_star') or 0),
                                   -(c.get('sold_count') or 0), c['id']))

    def publish(candidate):
        item = public_product(candidate)
        raw_id = candidate['raw_item_id']
        if raw_id in score_map:
            item['p_click'] = score_map[raw_id]
            item['recommendation_source'] = 'ai'
        else:
            item['recommendation_source'] = 'catalog'
        return item

    is_golf = 'golf' in focus_name.lower()
    selected_items = []
    seen_templates = {focus_disp['template_id']} if focus_disp else {focus['id']}
    seen_names = {focus_name.strip().lower()}

    if is_golf:
        for c in candidates:
            cdisp = displays.get(c['id'])
            cname = cdisp['name'] if cdisp else c['name']
            if 'golf' in cname.lower() and cdisp and cdisp['template_id'] not in seen_templates:
                selected_items.append(publish(c))
                seen_templates.add(cdisp['template_id'])
                seen_names.add(cname.strip().lower())
                break

    for t in target_types:
        for c in candidates:
            cdisp = displays.get(c['id'])
            if not cdisp:
                continue
            if cdisp['presentation_type'] == t and cdisp['template_id'] not in seen_templates:
                cname = cdisp['name'].strip().lower()
                if cname not in seen_names:
                    selected_items.append(publish(c))
                    seen_templates.add(cdisp['template_id'])
                    seen_names.add(cname)
                    break
        if len(selected_items) >= 4:
            break

    if len(selected_items) < 3:
        for fallback_t in CATEGORY_COMPLEMENTARY_FALLBACK.get(focus_cat, []):
            if fallback_t in target_types:
                continue
            for c in candidates:
                cdisp = displays.get(c['id'])
                if not cdisp:
                    continue
                if cdisp['presentation_type'] == fallback_t and cdisp['template_id'] not in seen_templates:
                    cname = cdisp['name'].strip().lower()
                    if cname not in seen_names:
                        selected_items.append(publish(c))
                        seen_templates.add(cdisp['template_id'])
                        seen_names.add(cname)
                        break
            if len(selected_items) >= 4:
                break

    if focus_source == 'cart':
        bundle_label = f"Combo mua kèm sản phẩm trong giỏ hàng: {focus_name}"
    elif focus_source == 'order':
        bundle_label = f"Gợi ý phụ kiện đi kèm hóa đơn gần đây: {focus_name}"
    elif focus_source == 'wishlist':
        bundle_label = f"Gợi ý combo cho sản phẩm trong mục yêu thích: {focus_name}"
    elif focus_source == 'history':
        bundle_label = f"Gợi ý combo dựa trên sản phẩm bạn vừa xem: {focus_name}"
    else:
        bundle_label = f"Combo mua kèm tiết kiệm cùng {focus_name}"

    focus_pub = public_product(focus)
    total_original = focus_pub['original_price'] + sum(p['original_price'] for p in selected_items)
    combo_price = int((focus_pub['price'] + sum(p['price'] for p in selected_items)) * 0.95)
    savings = total_original - combo_price
    discount_pct = round((savings / total_original) * 100) if total_original > 0 else 5

    return {
        'focus': focus_pub,
        'bundle_label': bundle_label,
        'focus_source': focus_source,
        'accessory_types': target_types,
        'items': selected_items,
        'model_used': bool(score_map),
        'pricing': {
            'original_total': total_original,
            'bundle_total': combo_price,
            'savings': savings,
            'discount_percent': discount_pct
        }
    }


# ---------------------------------------------------------------------------
# Shopee-style personalised feed. Display ordering only: raw MUSE scores
# (p_click / similarity) are never modified, only the visible order changes.
# ---------------------------------------------------------------------------
ACTION_WEIGHTS = {'click': 1.0, 'favorite': 2.0, 'add_to_cart': 2.5, 'purchase': 3.0}


def _context_boundary(db):
    setting = db.execute("SELECT value FROM catalog_settings WHERE key='storefront_context'").fetchone()
    if setting:
        return json.loads(setting[0])['after_behavior_id']
    return db.execute('SELECT COALESCE(MAX(id),0) FROM user_behavior_history').fetchone()[0]


def _normalize(weights):
    top = max(weights.values(), default=0)
    return {k: round(v / top, 4) for k, v in weights.items() if v > 0} if top > 0 else {}


def _search_index(displays):
    index = {}
    for d in displays.values():
        kind = d.get('presentation_type')
        if kind:
            index[d['template_id']] = (d['name'].casefold(), TYPE_LABELS.get(kind, '').casefold(), kind)
    return list(index.values())


def _types_for_query(query, index):
    q = (query or '').strip().casefold()
    if len(q) < 2:
        return set()
    return {kind for name, label, kind in index if q in name or (label and (q in label or label in q))}


def interest_profile(db, user_id, focus_product_id=None):
    """Weights per product type from views, wishlist, cart, orders and searches."""
    displays = presentation_map(str(config.DB_PATH))
    similar, complementary, signals = Counter(), Counter(), Counter()

    def add(product_id, weight, comp_factor, source):
        d = displays.get(product_id)
        kind = d.get('presentation_type') if d else None
        if not kind:
            return
        similar[kind] += weight
        for i, other in enumerate(COMPLEMENTARY_TYPE_MAP.get(kind, [])[:4]):
            if other != kind:
                complementary[other] += weight * comp_factor * (1 - 0.15 * i)
        signals[source] += 1

    if focus_product_id:
        add(focus_product_id, 3.0, 0.6, 'focus')
    if user_id:
        rows = db.execute('''SELECT product_id,action_type FROM user_behavior_history
            WHERE user_id=? AND id>? AND action_type IN ('click','favorite','add_to_cart','purchase')
            ORDER BY id DESC LIMIT 40''', (user_id, _context_boundary(db))).fetchall()
        for i, r in enumerate(rows):
            add(r['product_id'], ACTION_WEIGHTS[r['action_type']] * (0.9 ** i), 0.5, 'behavior')
        for r in db.execute('SELECT product_id FROM wishlist WHERE user_id=? ORDER BY rowid DESC LIMIT 10', (user_id,)):
            add(r['product_id'], 1.5, 0.5, 'wishlist')
        for r in db.execute('SELECT product_id FROM cart_items WHERE user_id=? ORDER BY id DESC LIMIT 10', (user_id,)):
            add(r['product_id'], 2.5, 1.0, 'cart')
        for r in db.execute('''SELECT oi.product_id FROM order_items oi JOIN orders o ON o.id=oi.order_id
                WHERE o.user_id=? AND o.order_status!='Đã hủy' ORDER BY o.id DESC, oi.id DESC LIMIT 10''', (user_id,)):
            # A bought item mostly calls for accessories, less for another identical item.
            add(r['product_id'], 1.0, 1.2, 'order')
        queries = [r[0] for r in db.execute('''SELECT query FROM search_history WHERE user_id=?
            GROUP BY query ORDER BY MAX(id) DESC LIMIT 8''', (user_id,))]
        if queries:
            index = _search_index(displays)
            for i, q in enumerate(queries):
                for kind in _types_for_query(q, index):
                    similar[kind] += 1.5 * (0.85 ** i)
                    signals['search'] += 1
    return {'similar': _normalize(similar), 'complementary': _normalize(complementary), 'signals': dict(signals)}


def personalize_order(products, displays, profile, affinity=None, score_map=None, window=48, bonus=None):
    """Blend MUSE rank with shopping interest, then cap repeats of one type in the head."""
    if not products:
        return products
    n = len(products)
    if score_map:
        ranked = sorted(products, key=lambda p: (-score_map[p['raw_item_id']], p['id']))
    else:
        ranked = sorted(products, key=lambda p: (-(p.get('sold_count') or 0), -(p.get('rating_star') or 0), p['id']))
    base = {p['id']: 1 - i / n for i, p in enumerate(ranked)}
    sim, comp = profile.get('similar', {}), profile.get('complementary', {})
    use_price = affinity and affinity.get('tier') != 'all'

    def final(p):
        d = displays.get(p['id'])
        kind = d.get('presentation_type') if d else None
        price = d['price'] if d else p['price']
        s = 0.45 * base[p['id']] + 0.40 * sim.get(kind, 0) + 0.22 * comp.get(kind, 0)
        if use_price and affinity['min_price'] <= price <= affinity['max_price']:
            s += 0.08
        return s + (bonus(p) if bonus else 0)

    scored = {p['id']: final(p) for p in products}
    ordered = distinct_illustrations(sorted(products, key=lambda p: (-scored[p['id']], p['id'])))
    kind_of = lambda p: (displays.get(p['id']) or {}).get('presentation_type') or 'other'
    counts, head, pool = Counter(), [], ordered[:max(window * 3, 60)]
    rest = ordered[len(pool):]
    while pool and len(head) < window:
        # Each repeat of a type costs a little, the item just shown costs more.
        last = kind_of(head[-1]) if head else None
        best = max(pool, key=lambda p: scored[p['id']] - 0.07 * counts[kind_of(p)]
                   - (0.12 if kind_of(p) == last else 0)
                   - (1.0 if counts[kind_of(p)] >= (6 if sim.get(kind_of(p), 0) >= 0.8 else 4) else 0))
        pool.remove(best)
        counts[kind_of(best)] += 1
        head.append(best)
    return head + pool + rest


def feed_candidates(db, products, user_id, touchpoint, target, focus_product_id=None):
    """Same-type items plus accessories for product page, cart and order pages."""
    displays = presentation_map(str(config.DB_PATH))
    if not displays:
        return None, {'enabled': False, 'reason': 'no_presentation'}
    primary, excluded, source, focus = [], set(), 'browse', None
    if touchpoint in ('similar', 'complementary') and target:
        focus = displays.get(target['id'])
        source = 'viewed_product' if touchpoint == 'similar' else 'purchased_product'
    elif touchpoint == 'home' and focus_product_id:
        focus = displays.get(focus_product_id)
        source = 'selected_product'
    if focus:
        primary.append(focus['presentation_type'])
        excluded.add(focus['template_id'])
    if touchpoint == 'cart' and user_id:
        source = 'cart'
        for r in db.execute('SELECT product_id FROM cart_items WHERE user_id=? ORDER BY id DESC', (user_id,)):
            d = displays.get(r['product_id'])
            if d:
                excluded.add(d['template_id'])
                if d['presentation_type'] not in primary:
                    primary.append(d['presentation_type'])
    secondary = []
    for kind in primary:
        for other in COMPLEMENTARY_TYPE_MAP.get(kind, []):
            if other not in primary and other not in secondary:
                secondary.append(other)
    context = {'enabled': True, 'mode': 'feed', 'source': source, 'label': 'Có thể bạn cũng thích',
               'types': primary, 'complementary_types': secondary,
               'focus_name': focus['name'] if focus else None,
               'deduplicate': 'illustrative_product', 'model_scores_unchanged': True,
               'scope_key': 'feed:' + source + ':' + ','.join(primary)}
    if not primary:
        return None, context
    allowed = set(primary) | set(secondary)
    ids = {p['id'] for p in products if (d := displays.get(p['id']))
           and d['presentation_type'] in allowed and d['template_id'] not in excluded}
    return ids, context


def _interleave(primary, secondary, pattern):
    out, i, j, k = [], 0, 0, 0
    while i < len(primary) or j < len(secondary):
        want = pattern[k % len(pattern)]
        k += 1
        if (want == 'P' and i < len(primary)) or j >= len(secondary):
            out.append(primary[i]); i += 1
        else:
            out.append(secondary[j]); j += 1
    return out


def mix_feed(products, displays, context, touchpoint):
    """products are already in score order; same type first, accessories rotate by type."""
    primary = set(context.get('types') or [])
    if not primary:
        return distinct_illustrations(products)
    kind = lambda p: (displays.get(p['id']) or {}).get('presentation_type')
    same = distinct_illustrations([p for p in products if kind(p) in primary])
    groups = {t: distinct_illustrations([p for p in products if kind(p) == t]) for t in context.get('complementary_types') or []}
    rotated = []
    while any(groups.values()):
        for t in list(groups):
            if groups[t]:
                rotated.append(groups[t].pop(0))
    pattern = {'similar': 'PPS', 'cart': 'PS', 'complementary': 'SP'}.get(touchpoint, 'PPS')
    return distinct_illustrations(_interleave(same, rotated, pattern))


def sale_progress(product_id):
    return 35 + (product_id * 37) % 58


def personalized_deals(db, user_id, limit=12):
    from app.database import public_product
    from app.recommender.service import service
    displays = presentation_map(str(config.DB_PATH))
    affinity = user_price_affinity(db, user_id)
    in_cart = {r[0] for r in db.execute('SELECT product_id FROM cart_items WHERE user_id=?', (user_id,))} if user_id else set()

    if not displays:
        cat_weights = Counter()
        signal_counts = Counter()
        if user_id:
            hist = db.execute('''SELECT h.action_type, p.category_id FROM user_behavior_history h
                JOIN products p ON p.id=h.product_id
                WHERE h.user_id=? AND h.action_type IN ('demo_interest','click','favorite','add_to_cart','purchase')
                ORDER BY h.id DESC LIMIT 24''', (user_id,)).fetchall()
            for idx, r in enumerate(hist):
                w = {'demo_interest': 4.0, 'purchase': 3.0, 'add_to_cart': 2.5, 'favorite': 2.0, 'click': 1.2}.get(r['action_type'], 1.0)
                cat_weights[r['category_id']] += w * (0.9 ** idx)
                signal_counts[r['action_type']] += 1

        candidates = []
        seen_ids = set(in_cart)
        top_cats = [cid for cid, _ in cat_weights.most_common(4)]
        for cid in top_cats:
            for r in db.execute('''SELECT p.*, c.name category_name, pr.name province_name FROM products p
                JOIN categories c ON c.id=p.category_id
                LEFT JOIN provinces pr ON pr.id=p.province_id
                WHERE p.category_id=? AND p.id <= 50000 AND p.stock>0 AND p.discount_percent>=20
                ORDER BY p.discount_percent DESC, p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 35''', (cid,)):
                if r['id'] not in seen_ids:
                    seen_ids.add(r['id'])
                    candidates.append(dict(r))

        for r in db.execute('''SELECT p.*, c.name category_name, pr.name province_name FROM products p
            JOIN categories c ON c.id=p.category_id
            LEFT JOIN provinces pr ON pr.id=p.province_id
            WHERE p.id <= 50000 AND p.stock>0 AND p.discount_percent>=25
            ORDER BY p.discount_percent DESC, p.rating_star DESC, p.sold_count DESC, p.id ASC LIMIT 120'''):
            if r['id'] not in seen_ids:
                seen_ids.add(r['id'])
                candidates.append(dict(r))

        p_click_map = {}
        model = service.model
        if model and user_id and candidates:
            try:
                model.items.register_products(candidates)
                valid_raw = [c['raw_item_id'] for c in candidates if c['raw_item_id'] in model.items]
                if valid_raw:
                    scores, _ = model.predict(user_id, valid_raw[:128])
                    p_click_map = dict(zip(valid_raw[:128], scores))
            except Exception:
                pass

        max_cat_w = max(cat_weights.values(), default=1.0)
        use_price = affinity and affinity.get('tier') != 'all'

        def deal_score(p):
            pc = p_click_map.get(p['raw_item_id'], 0.0)
            cat_s = cat_weights.get(p['category_id'], 0.0) / max_cat_w if cat_weights else 0.0
            disc_s = min(p.get('discount_percent', 0) / 60.0, 1.0)
            price_fit = 0.12 if (use_price and affinity['min_price'] <= p['price'] <= affinity['max_price']) else 0.0
            jitter = random.uniform(-0.06, 0.06)
            return 0.45 * pc + 0.35 * cat_s + 0.20 * disc_s + price_fit + jitter

        def core_deal_title(name: str) -> str:
            s = re.sub(r'[\(\[\{].*?[\)\]\}]', ' ', name or '')
            if ' - ' in s:
                s = s.split(' - ')[0]
            return ' '.join(s.split()).lower()

        candidates.sort(key=lambda p: (deal_score(p), p.get('discount_percent', 0), p.get('sold_count', 0)), reverse=True)

        items = []
        seen_names = set()
        seen_cores = set()
        cat_cap = Counter()
        for pass_idx in (1, 2):
            for p in candidates:
                cname = p['name'].strip().lower()
                core = core_deal_title(p['name'])
                if cname in seen_names or (core and core in seen_cores):
                    continue
                if pass_idx == 1 and cat_cap[p['category_id']] >= 2:
                    continue
                rid = p['raw_item_id']
                if rid in p_click_map:
                    p['p_click'] = round(p_click_map[rid], 6)
                p['price_tier_match'] = bool(use_price and affinity['min_price'] <= p['price'] <= affinity['max_price'])
                p['recommendation_source'] = 'ai' if (user_id and p_click_map) else 'catalog'
                if p['category_id'] in top_cats[:2]:
                    p['recommendation_reason'] = f"Flash Sale hợp gu {p.get('category_name', '')} · Giảm {p['discount_percent']}%"
                elif p['price_tier_match']:
                    p['recommendation_reason'] = f"Ưu đãi hợp túi tiền · Giảm {p['discount_percent']}%"
                else:
                    p['recommendation_reason'] = f"Deal hot hôm nay · Giảm {p['discount_percent']}%"
                item = public_product(p)
                seen_names.add(cname)
                if core:
                    seen_cores.add(core)
                cat_cap[p['category_id']] += 1
                item['sale_progress'] = sale_progress(p['id'])
                items.append(item)
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break

        return {
            'items': items,
            'personalized': bool(user_id and (cat_weights or p_click_map)),
            'price_affinity': affinity,
            'signals': dict(signal_counts)
        }

    rows = [dict(r) for r in db.execute('''SELECT p.*,c.name category_name FROM products p
        JOIN categories c ON c.id=p.category_id JOIN product_presentations d ON d.product_id=p.id
        WHERE p.stock>0 AND p.source_feature_complete=1 AND d.original_price>d.price''')]
    rows = [p for p in rows if p['id'] not in in_cart]
    profile = interest_profile(db, user_id)

    def discount(p):
        d = displays.get(p['id'])
        return round((d['original_price'] - d['price']) * 100 / d['original_price']) if d and d['original_price'] else 0

    def bonus(p):
        d = displays.get(p['id'])
        price = d['price'] if d else p['price']
        outside = affinity.get('tier') != 'all' and not (affinity['min_price'] <= price <= affinity['max_price'])
        return 0.2 * discount(p) / 50 - (0.15 if outside else 0)

    ordered = personalize_order(rows, displays, profile, affinity, None, window=limit, bonus=bonus)
    items = []
    for p in ordered[:limit]:
        item = public_product(p)
        item['sale_progress'] = sale_progress(p['id'])
        items.append(item)
    return {'items': items, 'personalized': bool(profile['signals']),
            'price_affinity': affinity, 'signals': profile['signals']}
