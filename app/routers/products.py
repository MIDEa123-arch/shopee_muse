import unicodedata
import re
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from app.database import connection, public_product
from app.security import current_user, require_user
from app.recommender.service import service
from app.native_catalog import MODE,catalog_info,identity_svg
from fastapi.responses import Response
from app import config
from app.storefront import available_categories, TYPE_LABELS, presentation_map
from app.recommender.commerce import distinct_illustrations

router=APIRouter(prefix='/api',tags=['catalog'])
PRODUCT_SQL='''SELECT p.*,c.name category_name,pr.name province_name FROM products p
    LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN provinces pr ON pr.id=p.province_id
    LEFT JOIN product_presentations d ON d.product_id=p.id'''


_CATEGORY_COUNTS_CACHE = {
    1: 200000,
    2: 240000,
    3: 240000,
    4: 240000,
    5: 160000,
    6: 240000,
    7: 200000,
    8: 120000,
    9: 200000,
    10: 80000,
    11: 80000,
}
_GLOBAL_TOTAL_CACHE = sum(_CATEGORY_COUNTS_CACHE.values())
def _is_large_vietnam_catalog(info):
    return info.get('mode') == 'vietnam_tiki_v1'


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower().replace('đ','d')) if unicodedata.category(c)!='Mn')


def search_text(text):
    """Normalized searchable words with boundaries for safe prefix matching."""
    return ' '+' '.join(re.findall(r'[a-z0-9]+',normalize(str(text or ''))))+' '


def extract_search_keyword(name: str) -> str:
    cleaned = re.split(r'[\(\[\-–]', name)[0].strip()
    words = cleaned.split()
    return ' '.join(words[:6]) if len(words) > 6 else cleaned


def lexical_score(query: str, name: str, brand: str = '') -> float:
    nq = normalize(query).strip()
    words_q = nq.split()
    if not words_q:
        return 0.0
    name_norm = normalize(name)
    name_words = name_norm.split()
    score = 0.0
    if name_norm.startswith(nq):
        score += 3.0
    elif nq in name_norm:
        score += 1.0
    matched_exact = sum(1 for w in words_q if w in name_words)
    matched_prefix = sum(1 for w in words_q if any(nw.startswith(w) for nw in name_words))
    score += matched_exact * 2.0 + matched_prefix * 0.5
    if brand and normalize(brand) in words_q:
        score += 1.0
    return score


@router.get('/catalog')
def catalog():
    with connection() as db:
        info = catalog_info(db)
        native = info['mode'] == MODE
        if native:
            cats = [dict(r) for r in db.execute('SELECT c.*,COUNT(p.id) product_count FROM categories c JOIN products p ON p.category_id=c.id WHERE p.stock>0 AND (p.catalog_source IS NULL OR p.source_feature_complete=1) GROUP BY c.id ORDER BY product_count DESC,c.id')]
            total = db.execute('SELECT COUNT(*) FROM products WHERE stock>0 AND (catalog_source IS NULL OR source_feature_complete=1)').fetchone()[0]
        elif _is_large_vietnam_catalog(info):
            info={**info,'real_images':False,'real_titles':False,'semantic_mapping_verified':False,
                  'metadata_role':'illustrative_generated_merchandise_not_original_taobao'}
            cats = [dict(c) for c in db.execute('SELECT * FROM categories WHERE id <= 11 ORDER BY id')]
            for c in cats:
                c['product_count'] = _CATEGORY_COUNTS_CACHE.get(c['id'], 0)
            total = _GLOBAL_TOTAL_CACHE
        else:
            cats = [dict(r) for r in db.execute('''SELECT c.*,COUNT(p.id) product_count
                FROM categories c LEFT JOIN products p ON p.category_id=c.id AND p.stock>0
                GROUP BY c.id ORDER BY c.id''')]
            total = db.execute('SELECT COUNT(*) FROM products WHERE stock>0').fetchone()[0]

        return {'source':info,
                'presentation':json.loads(r['value']) if (r:=db.execute("SELECT value FROM catalog_settings WHERE key='storefront'").fetchone()) else None,
                'storefront_categories':available_categories(db),
                'categories':cats,
                'provinces':[dict(r) for r in db.execute('SELECT * FROM provinces ORDER BY id')],
                'product_count':total}


@router.get('/item-art/{product_id}.svg')
def item_art(product_id:int):
    with connection() as db:
        row=db.execute('SELECT category_id FROM products WHERE id=? AND catalog_source=?',(product_id,'taobao-mm')).fetchone()
    if not row:
        raise HTTPException(404,'Mẫu không tồn tại.')
    return Response(identity_svg(product_id,row[0]),media_type='image/svg+xml',
                    headers={'Cache-Control':'public,max-age=3600'})


class SearchHistoryPayload(BaseModel):
    query: str = Field(min_length=1, max_length=100)


@router.get('/search/suggestions')
def search_suggestions(q:str=Query('',max_length=100),user=Depends(current_user)):
    with connection() as db:
        db.create_function('normalize',1,normalize)
        db.create_function('search_text',1,search_text)
        history=[]
        if user:
            rows=db.execute('SELECT query FROM search_history WHERE user_id=? ORDER BY id DESC LIMIT 8',(user['id'],)).fetchall()
            history=list(dict.fromkeys(r['query'] for r in rows))

        trending=[
            'tai nghe bluetooth','áo thun nam','bàn phím cơ','kem chống nắng',
            'nồi chiên không dầu','giày sneaker','robot hút bụi','đồng hồ nam'
        ]
        source_info=catalog_info(db)
        native=source_info['mode']==MODE
        if _is_large_vietnam_catalog(source_info):
            from app.recommender.retail import catalog_candidates, _distinct, query_matches
            if not q.strip():
                result=service.recommend(user['id'] if user else None,limit=6,write_logs=False)
                suggested=result['items']
            else:
                candidates=[p for p in catalog_candidates(db) if query_matches(p,q)]
                candidates.sort(key=lambda p:(lexical_score(q,p['name']),p['sold_count'],-p['id']),reverse=True)
                if user:candidates=service.rank_search_candidates(user['id'],candidates)
                suggested=_distinct([public_product(p) for p in candidates],6)
            words=list(dict.fromkeys(p['name'] for p in suggested))
            return {'history':history,'trending':trending,'personalized':words[:4] or trending[:4],
                    'autocomplete':words[:8] if q.strip() else [],'products':suggested,
                    'suggestion_context':{'mode':'typed_query' if q.strip() else 'current_merchandise_context',
                                          'title':'Sản phẩm phù hợp' if q.strip() else 'Có thể bạn quan tâm',
                                          'subtitle':'','signals':[]}}
        product_columns={r['name'] for r in db.execute('PRAGMA table_info(products)')}
        has_brand='brand' in product_columns
        if native and not available_categories(db):
            trending=[r[0] for r in db.execute('SELECT name FROM categories WHERE id>=10001 ORDER BY id LIMIT 6')]
        elif native:
            trending=['tai nghe','áo sơ mi','nước hoa','đèn bàn','giày','túi xách']

        personalized=[]
        top_user_cats=[]
        if user:
            displays = presentation_map(str(config.DB_PATH))
            recent_items = db.execute('''SELECT DISTINCT h.product_id, p.category_id, COALESCE(d.name, p.name) name
                FROM user_behavior_history h
                JOIN products p ON p.id = h.product_id
                LEFT JOIN product_presentations d ON d.product_id = p.id
                WHERE h.user_id = ? AND h.action_type IN ('demo_interest','click','favorite','add_to_cart','purchase')
                ORDER BY h.id DESC LIMIT 12''', (user['id'],)).fetchall()
            for r in recent_items:
                if r['category_id'] and r['category_id'] not in top_user_cats:
                    top_user_cats.append(r['category_id'])
                name = r['name']
                words = name.split()
                short_keyword = ' '.join(words[:4]) if len(words) > 4 else name
                if short_keyword and short_keyword not in personalized:
                    personalized.append(short_keyword)
                disp = displays.get(r['product_id'])
                ptype = disp.get('presentation_type') if disp else None
                if ptype and ptype in TYPE_LABELS:
                    label = TYPE_LABELS[ptype]
                    if label not in personalized:
                        personalized.append(label)
                if len(personalized) >= 6:
                    break

            top_cats=db.execute('''SELECT p.category_id,COUNT(*) cnt FROM user_behavior_history h
                JOIN products p ON p.id=h.product_id WHERE h.user_id=?
                GROUP BY p.category_id ORDER BY cnt DESC LIMIT 4''',(user['id'],)).fetchall()
            for c in top_cats:
                if c['category_id'] not in top_user_cats:
                    top_user_cats.append(c['category_id'])

            if not personalized:
                cat_map={
                    1:['laptop mỏng nhẹ','macbook pro','bàn phím cơ'],
                    2:['tai nghe bluetooth','loa di động jbl','tai nghe chống ồn'],
                    3:['áo thun nam coolmate','áo polo nam','quần tây nam'],
                    4:['váy đầm tiểu thư','áo blazer nữ','chân váy chữ a'],
                    5:['giày sneaker biti\'s','giày chạy bộ nike','giày cao gót juno'],
                    6:['nồi chiên không dầu philips','bình giữ nhiệt lock&lock','robot hút bụi dreame'],
                    7:['serum phục hồi b5','kem chống nắng anessa','son kem lì black rouge'],
                    8:['đồng hồ casio edifice','đồng hồ citizen eco-drive'],
                    9:['iphone 15 pro max','samsung galaxy s24','máy tính bảng ipad'],
                    10:['đồ chơi xếp hình lego','tã dán moony bé'],
                    11:['vợt cầu lông yonex','lều cắm trại naturehike']
                }
                if native and not available_categories(db):
                    personalized=[r[0] for r in db.execute('''SELECT c.name FROM categories c JOIN products p ON p.category_id=c.id
                        JOIN user_behavior_history h ON h.product_id=p.id WHERE h.user_id=?
                        AND p.source_feature_complete=1 AND p.stock>0
                        GROUP BY c.id ORDER BY COUNT(*) DESC,c.id LIMIT 4''',(user['id'],))]
                for c in top_cats if not native else []:
                    personalized.extend(cat_map.get(c['category_id'],[]))
            personalized=list(dict.fromkeys(personalized))[:6]

        autocomplete=[]
        suggested_products=[]
        suggestion_context={}
        clean_q=q.strip()

        if clean_q:
            norm_q=normalize(clean_q)
            terms=[t for t in norm_q.split() if t]
            bound_clause = 'p.stock>0' if native else 'p.id <= 15000 AND +p.stock>0'
            term_clauses=[]
            term_params=[]
            exact_phrase = None
            if not native and len(terms)>1:
                phrase='% '+norm_q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                if db.execute("SELECT 1 FROM products p WHERE p.id<=15000 AND +p.stock>0 AND search_text(p.name) LIKE ? ESCAPE '\\' LIMIT 1",(phrase,)).fetchone():
                    exact_phrase=phrase
                    term_clauses.append("search_text(p.name) LIKE ? ESCAPE '\\'")
                    term_params.append(phrase)
            for t in ([] if exact_phrase else terms):
                esc = '%'+t.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                if native:
                    term_clauses.append("normalize(COALESCE(d.name,p.name) || ' ' || COALESCE(d.category_name,c.name,'')) LIKE ? ESCAPE '\\'")
                    term_params.append(esc)
                elif has_brand:
                    prefix='% '+t.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                    term_clauses.append("(search_text(p.name) LIKE ? ESCAPE '\\' OR search_text(p.brand) LIKE ? ESCAPE '\\')")
                    term_params.extend([prefix, prefix])
                else:
                    prefix='% '+t.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                    term_clauses.append("search_text(p.name) LIKE ? ESCAPE '\\'")
                    term_params.append(prefix)
            where_sql = ' AND '.join(term_clauses) if term_clauses else '1=1'
            order_sql = 'p.sold_count DESC, p.rating_star DESC, p.id ASC' if native else '+p.sold_count DESC, +p.rating_star DESC, p.id ASC'
            raw_rows = [dict(r) for r in db.execute(
                PRODUCT_SQL + f' WHERE {bound_clause} AND {where_sql} ORDER BY {order_sql} LIMIT 36',
                term_params
            ).fetchall()]

            if raw_rows:
                raw_rows.sort(
                    key=lambda r: (
                        lexical_score(clean_q, r['name'], r.get('brand') or ''),
                        r.get('sold_count', 0)
                    ),
                    reverse=True
                )
                if user and service.model:
                    raw_rows = service.rank_search_candidates(user['id'], raw_rows)
                    raw_rows.sort(
                        key=lambda r: (
                            lexical_score(clean_q, r['name'], r.get('brand') or '') >= 2.0,
                            (r.get('p_click') or 0.0),
                            lexical_score(clean_q, r['name'], r.get('brand') or ''),
                            r.get('sold_count', 0)
                        ),
                        reverse=True
                    )
                    for r in raw_rows:
                        if r.get('p_click') is not None:
                            r['recommendation_reason'] = f"Phù hợp với từ khóa “{clean_q}”"
                        else:
                            r['recommendation_reason'] = f"Khớp từ khóa “{clean_q}”"
                else:
                    for r in raw_rows:
                        r['recommendation_reason'] = f"Bán chạy cho “{clean_q}”"

            seen_names=set()
            seen_photos=set()
            seen_kws=set()
            for pass_idx in (1, 2):
                for r in raw_rows:
                    cname = (r.get('name') or '').strip().lower()
                    if not cname or cname in seen_names:
                        continue
                    pub = public_product(r)
                    if pass_idx == 1 and pub['image_url'] in seen_photos:
                        continue
                    seen_names.add(cname)
                    seen_photos.add(pub['image_url'])
                    kw = extract_search_keyword(pub['name'])
                    if kw.lower() not in seen_kws and len(autocomplete) < 6:
                        seen_kws.add(kw.lower())
                        autocomplete.append(kw)
                    if len(suggested_products) < 6:
                        suggested_products.append(pub)
                    if len(suggested_products) >= 6 and len(autocomplete) >= 6:
                        break
                if len(suggested_products) >= 6:
                    break

            suggestion_context = {
                'mode': 'query_personalized_rerank' if (user and service.model) else 'query_instant_match',
                'title': f'Sản phẩm gợi ý cho “{clean_q}”',
                'subtitle': 'Ưu tiên kết quả khớp từ khóa và hoạt động mua sắm gần đây' if (user and service.model) else 'Sản phẩm khớp từ khóa có lượt mua cao',
                'signals': ['Khớp từ khóa', 'Hoạt động gần đây', 'Mức độ phổ biến'] if user else ['Khớp từ khóa', 'Lượt bán và đánh giá']
            }
        else:
            # Zero-query visual product cards when user focuses/clicks the search bar
            raw_candidates=[]
            seen_ids=set()
            if user and top_user_cats:
                for cid in top_user_cats[:3]:
                    rows = db.execute(
                        PRODUCT_SQL + ' WHERE p.category_id=? AND p.id <= 15000 AND +p.stock>0 ORDER BY +p.rating_star DESC, +p.sold_count DESC, p.id ASC LIMIT 16',
                        (cid,)
                    ).fetchall()
                    for r in rows:
                        if r['id'] not in seen_ids:
                            seen_ids.add(r['id'])
                            raw_candidates.append(dict(r))
            rows = db.execute(
                PRODUCT_SQL + ' WHERE p.id <= 10000 AND +p.stock>0 ORDER BY +p.rating_star DESC, +p.sold_count DESC, p.id ASC LIMIT 24'
            ).fetchall()
            for r in rows:
                if r['id'] not in seen_ids:
                    seen_ids.add(r['id'])
                    raw_candidates.append(dict(r))

            if user and service.model and raw_candidates:
                raw_candidates = service.rank_search_candidates(user['id'], raw_candidates)
                primary_cat = top_user_cats[0] if top_user_cats else None
                secondary_cat = top_user_cats[1] if len(top_user_cats) > 1 else None
                raw_candidates.sort(
                    key=lambda x: (
                        (x.get('p_click') or 0.0)
                        + (0.18 if x.get('category_id') == primary_cat else 0.08 if x.get('category_id') == secondary_cat else 0.0),
                        x.get('sold_count', 0)
                    ),
                    reverse=True
                )
                for r in raw_candidates:
                    if r.get('category_id') in top_user_cats[:2]:
                        r['recommendation_reason'] = f"Gần với sản phẩm bạn quan tâm trong {r.get('category_name') or 'danh mục này'}"
                    else:
                        r['recommendation_reason'] = 'Có thể bạn sẽ quan tâm'
            else:
                for r in raw_candidates:
                    r['recommendation_reason'] = 'Xu hướng tìm kiếm nổi bật'

            seen_names=set()
            seen_photos=set()
            cat_counts={}
            for pass_idx in (1, 2):
                for r in raw_candidates:
                    cname = (r.get('name') or '').strip().lower()
                    cid = r.get('category_id')
                    if not cname or cname in seen_names:
                        continue
                    if pass_idx == 1 and cat_counts.get(cid, 0) >= 3:
                        continue
                    pub = public_product(r)
                    if pass_idx == 1 and pub['image_url'] in seen_photos:
                        continue
                    seen_names.add(cname)
                    seen_photos.add(pub['image_url'])
                    cat_counts[cid] = cat_counts.get(cid, 0) + 1
                    suggested_products.append(pub)
                    if len(suggested_products) >= 6:
                        break
                if len(suggested_products) >= 6:
                    break

            suggestion_context = {
                'mode': 'zero_query_personalized' if user else 'zero_query_trending',
                'title': 'Có thể bạn quan tâm' if user else 'Sản phẩm đang được quan tâm',
                'subtitle': 'Dựa trên sản phẩm đã xem, giỏ hàng và từ khóa gần đây' if user else 'Các sản phẩm có lượt tìm kiếm và đánh giá cao hôm nay',
                'signals': ['Hoạt động gần đây', 'Ngành hàng thường xem', 'Mức độ phổ biến'] if user else ['Tìm kiếm phổ biến', 'Đánh giá tốt']
            }

        return {
            'history':history,
            'trending':trending,
            'personalized':personalized or trending[:4],
            'autocomplete':autocomplete,
            'products':suggested_products,
            'suggestion_context':suggestion_context
        }


@router.post('/search/history')
def save_search_history(payload:SearchHistoryPayload,user=Depends(current_user)):
    q=payload.query.strip()
    if user and q:
        with connection(write=True) as db:
            db.execute('DELETE FROM search_history WHERE user_id=? AND query=?',(user['id'],q))
            db.execute('INSERT INTO search_history(user_id,query) VALUES (?,?)',(user['id'],q))
    return {'ok':True}


@router.delete('/search/history')
def delete_search_history(query:str|None=None,user=Depends(require_user)):
    with connection(write=True) as db:
        if query:
            db.execute('DELETE FROM search_history WHERE user_id=? AND query=?',(user['id'],query))
        else:
            db.execute('DELETE FROM search_history WHERE user_id=?',(user['id'],))
    return {'ok':True}


@router.get('/products')
def products(q:str=Query('',max_length=100),category_id:int|None=None,province_id:int|None=None,
             display_category:str=Query('',max_length=40),
             unique_products:bool=False,
             min_price:int=Query(0,ge=0),max_price:int|None=Query(None,ge=0),
             sort:str=Query('popular',pattern='^(popular|relevance|price_asc|price_desc|newest|sold|rating|discount)$'),
             page:int=Query(1,ge=1),page_size:int=Query(24,ge=1,le=60),mall:bool=False,
             freeship:bool=False,
             user=Depends(current_user)):
    with connection() as db:
        db.create_function('normalize',1,normalize)
        db.create_function('search_text',1,search_text)
        source_info=catalog_info(db)
        native=source_info['mode']==MODE
        has_brand=bool(db.execute("SELECT 1 FROM pragma_table_info('products') WHERE name='brand'").fetchone())
        search_bound=50000 if unique_products and _is_large_vietnam_catalog(source_info) else 25000

        clauses=['p.stock>0'];params=[]
        for column,value in [('category_id',category_id),('province_id',province_id)]:
            if value is not None:
                clauses.append(f'p.{column}=?');params.append(value)
        if min_price and min_price > 0:
            clauses.append('COALESCE(d.price,p.price)>=?' if native else 'p.price>=?');params.append(min_price)
        if max_price is not None:
            clauses.append('COALESCE(d.price,p.price)<=?' if native else 'p.price<=?');params.append(max_price)
        if display_category and native:
            clauses.append('d.category_slug=?');params.append(display_category)
        if mall:
            clauses.append('p.is_mall=1')
        if freeship:
            clauses.append('p.is_freeship=1')

        if native:
            order_map={'popular':'p.rating_star DESC,p.sold_count DESC','relevance':'p.sold_count DESC',
                       'price_asc':'COALESCE(d.price,p.price) ASC','price_desc':'COALESCE(d.price,p.price) DESC',
                       'newest':'p.id DESC','sold':'p.sold_count DESC','rating':'p.rating_star DESC,p.rating_count DESC',
                       'discount':'CASE WHEN d.original_price>d.price THEN (d.original_price-d.price)*1.0/d.original_price ELSE p.discount_percent/100.0 END DESC,p.sold_count DESC'}
            clauses.append('p.source_feature_complete=1')
            if sort=='discount':
                clauses.append('d.original_price>d.price')
        else:
            order_map={'popular':'p.rating_star DESC,p.sold_count DESC','relevance':'p.sold_count DESC',
                       'price_asc':'p.price ASC','price_desc':'p.price DESC',
                       'newest':'p.id DESC','sold':'p.sold_count DESC','rating':'p.rating_star DESC,p.rating_count DESC',
                       'discount':'p.discount_percent DESC,p.sold_count DESC'}
        order=order_map.get(sort,'p.rating_star DESC,p.sold_count DESC')

        normalized_query=normalize(q).strip()
        query_terms=normalized_query.split()
        group_query=re.fullmatch(r'nhom\s*(\d{1,4})',normalized_query) if native else None
        if group_query:
            clauses.append('p.category_id=?');params.append(10000+int(group_query[1]))
        exact_phrase=None
        if not native and not group_query and len(query_terms)>1:
            phrase='% '+normalized_query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
            if db.execute("SELECT 1 FROM products p WHERE p.id<=? AND +p.stock>0 AND search_text(p.name) LIKE ? ESCAPE '\\' LIMIT 1",(search_bound,phrase)).fetchone():
                exact_phrase=phrase
                clauses.append("search_text(p.name) LIKE ? ESCAPE '\\'")
                params.append(phrase)
        for term in [] if group_query or exact_phrase else query_terms:
            clean_term = '%'+term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
            if native:
                clauses.append("normalize(COALESCE(d.name,p.name) || ' ' || COALESCE(d.shop_name,p.shop_name) || ' ' || coalesce(d.category_name,c.name,'') || ' ' || p.name) LIKE ? ESCAPE '\\'")
                params.append(clean_term)
            elif has_brand:
                prefix='% '+term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                clauses.append("(search_text(p.name) LIKE ? ESCAPE '\\' OR search_text(p.shop_name) LIKE ? ESCAPE '\\' OR search_text(p.brand) LIKE ? ESCAPE '\\')")
                params.extend([prefix, prefix, prefix])
            else:
                prefix='% '+term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                clauses.append("(search_text(p.name) LIKE ? ESCAPE '\\' OR search_text(p.shop_name) LIKE ? ESCAPE '\\')")
                params.extend([prefix, prefix])
        has_extra_filter = bool(q.strip() or province_id or (min_price and min_price > 0) or max_price is not None or freeship or mall)
        if not native and has_extra_filter:
            clauses[0] = '+p.stock>0'
            clauses.insert(0, f'p.id <= {search_bound}')
            order = order.replace('p.rating_star', '+p.rating_star').replace('p.sold_count', '+p.sold_count')
        where=' WHERE '+' AND '.join(clauses)

        if unique_products and _is_large_vietnam_catalog(source_info):
            # A retail catalog page must not show 24 color/ID copies whose
            # generated specifications were removed from the displayed title.
            # Stream a bounded range and retain one actual matching offer per
            # model, after province/price/stock/search filters have been applied.
            from app.recommender.merchandise import identity
            from app.recommender.retail import query_matches
            selected=[];seen=set()
            bounded=where+' AND p.id<=50000'
            stable_order=order.replace('p.rating_star','+p.rating_star').replace('p.sold_count','+p.sold_count')
            sql=PRODUCT_SQL.replace('FROM products p','FROM products p NOT INDEXED')
            for row in db.execute(sql+bounded+' ORDER BY '+stable_order+',p.id',params):
                product=dict(row);key=identity(product)
                if q.strip() and not query_matches(product,q):continue
                if key in seen:continue
                seen.add(key);selected.append(product)
            if sort=='relevance' and user and service.model:
                selected=service.rank_search_candidates(user['id'],selected)
            total=len(selected);offset=(page-1)*page_size
            items=[public_product(p) for p in selected[offset:offset+page_size]]
            if user and q.strip() and page==1:
                # Preserve the existing explicit-search history behavior.
                with connection(write=True) as wdb:
                    wdb.execute('DELETE FROM search_history WHERE user_id=? AND query=?',(user['id'],q.strip()))
                    wdb.execute('INSERT INTO search_history(user_id,query) VALUES (?,?)',(user['id'],q.strip()))
            return {'items':items,'total':total,'page':page,'page_size':page_size,
                    'pages':(total+page_size-1)//page_size,'unique_products':True,
                    'personalized':any(p.get('recommendation_source')=='ai' for p in items)}

        if not has_extra_filter and not category_id and _is_large_vietnam_catalog(source_info):
            total = _GLOBAL_TOTAL_CACHE
        elif not has_extra_filter and category_id and _is_large_vietnam_catalog(source_info):
            total = _CATEGORY_COUNTS_CACHE.get(category_id, 0)
        elif not native:
            total=db.execute('SELECT COUNT(*) FROM products p'+where,params).fetchone()[0]
        else:
            total=db.execute('SELECT COUNT(*) FROM products p LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN product_presentations d ON d.product_id=p.id'+where,params).fetchone()[0]

        # Save search query if user is logged in
        if user and q.strip() and page==1:
            try:
                with connection(write=True) as wdb:
                    wdb.execute('DELETE FROM search_history WHERE user_id=? AND query=?',(user['id'],q.strip()))
                    wdb.execute('INSERT INTO search_history(user_id,query) VALUES (?,?)',(user['id'],q.strip()))
            except Exception:
                pass

        # Check if personalized search re-ranking applies
        use_relevance=sort=='relevance' and user is not None and service.model is not None
        if native and unique_products:
            candidates=[dict(r) for r in db.execute(PRODUCT_SQL+where+' ORDER BY '+order+',p.id',params)]
            if use_relevance and candidates:
                candidates=service.rank_search_candidates(user['id'],candidates)
            candidates=distinct_illustrations(candidates)
            total=len(candidates);start=(page-1)*page_size
            items=[public_product(r) for r in candidates[start:start+page_size]]
            return {'items':items,'total':total,'page':page,'page_size':page_size,
                    'pages':(total+page_size-1)//page_size,
                    'personalized':any(p.get('recommendation_source')=='ai' for p in items),
                    'unique_products':True}
        if use_relevance and total>0:
            # Re-rank a bounded prefix, then paginate the remaining matches in the
            # same deterministic order. The reported total covers both segments.
            candidate_order=' ORDER BY p.sold_count DESC,p.id' if native else ' ORDER BY +p.sold_count DESC,p.id'
            raw_candidates=[dict(r) for r in db.execute(PRODUCT_SQL+where+candidate_order+('' if native else ' LIMIT 120'),params)]
            ranked=service.rank_search_candidates(user['id'],raw_candidates)
            if q.strip():
                ranked.sort(
                    key=lambda r: (
                        lexical_score(q, r['name'], r.get('brand') or '') >= 2.0,
                        (r.get('p_click') or 0.0),
                        lexical_score(q, r['name'], r.get('brand') or ''),
                        r.get('sold_count', 0)
                    ),
                    reverse=True
                )
            start_idx=(page-1)*page_size
            end_idx=start_idx+page_size
            page_items=[public_product(r) for r in ranked[start_idx:end_idx]]
            if end_idx>len(ranked):
                offset=max(start_idx,len(ranked))
                remaining=page_size-len(page_items)
                tail=db.execute(PRODUCT_SQL+where+candidate_order+' LIMIT ? OFFSET ?',params+[remaining,offset])
                page_items.extend(public_product(r) for r in tail)
            personalized=any(p.get('recommendation_source')=='ai' for p in page_items)
            return {'items':page_items,'total':total,'page':page,'page_size':page_size,'pages':(total+page_size-1)//page_size,'personalized':personalized}

        rows=db.execute(PRODUCT_SQL+where+' ORDER BY '+order+',p.id LIMIT ? OFFSET ?',params+[page_size,(page-1)*page_size])
        return {'items':[public_product(r) for r in rows],'total':total,'page':page,'page_size':page_size,'pages':(total+page_size-1)//page_size,'personalized':False}


@router.get('/products/{product_id}')
def product(product_id:int):
    with connection() as db:
        row=db.execute(PRODUCT_SQL+' WHERE p.id=?',(product_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Sản phẩm không tồn tại.')
        result=public_product(row)
        result['reviews']=[dict(r) for r in db.execute('SELECT r.rating,r.content,r.created_at,u.full_name FROM reviews r JOIN users u ON u.id=r.user_id WHERE product_id=? ORDER BY r.id DESC LIMIT 20',(product_id,))]
        return result


_OFFERS_CACHE = None
_OFFERS_TIME = 0.0

@router.get('/offers')
def offers(user=Depends(current_user)):
    global _OFFERS_CACHE, _OFFERS_TIME
    with connection() as db:
        if _is_large_vietnam_catalog(catalog_info(db)):
            from app.recommender.commerce import personalized_deals
            return personalized_deals(db,user['id'] if user else None,6)
    import time
    now = time.monotonic()
    if _OFFERS_CACHE is not None and now - _OFFERS_TIME < 60.0:
        return _OFFERS_CACHE
    # Merchandising highlights use actual catalog prices, with one representative per photo.
    with connection() as db:
        rows=db.execute('''SELECT * FROM (
            SELECT p.*,pr.name province_name,ROW_NUMBER() OVER (
                PARTITION BY p.image_url ORDER BY p.discount_percent DESC,p.sold_count DESC,p.id) photo_rank
            FROM (
                SELECT * FROM products WHERE stock>0 AND discount_percent>0
                ORDER BY rating_star DESC, sold_count DESC, id ASC LIMIT 200
            ) p LEFT JOIN provinces pr ON pr.id=p.province_id
        ) WHERE photo_rank=1 ORDER BY discount_percent DESC,sold_count DESC,id LIMIT 6''')
        res = {'items':[public_product(row) for row in rows]}
        _OFFERS_CACHE = res
        _OFFERS_TIME = now
        return res


class Review(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    rating:int=Field(ge=1,le=5)
    content:str=Field(min_length=10,max_length=1000)


@router.post('/products/{product_id}/reviews',status_code=201)
def review(product_id:int,body:Review,user=Depends(require_user)):
    with connection(write=True) as db:
        if not db.execute("SELECT 1 FROM orders o JOIN order_items i ON i.order_id=o.id WHERE o.user_id=? AND i.product_id=? AND o.order_status='Đã giao'",(user['id'],product_id)).fetchone():
            raise HTTPException(403,'Bạn có thể đánh giá sau khi nhận sản phẩm.')
        if db.execute('SELECT 1 FROM reviews WHERE user_id=? AND product_id=?',(user['id'],product_id)).fetchone():
            raise HTTPException(409,'Bạn đã đánh giá sản phẩm này.')
        db.execute('INSERT INTO reviews(user_id,product_id,rating,content) VALUES (?,?,?,?)',(user['id'],product_id,body.rating,body.content.strip()))
    return {'ok':True}
