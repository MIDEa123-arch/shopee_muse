"""One bounded recall/filter/rank pipeline for the illustrative retail catalog.

Vietnamese merchandise labels were generated independently of Taobao features.
They are hard eligibility/context constraints, never inferred from SCL cosine.
Checkpoint probabilities are kept separate from the hybrid presentation score.
"""
import math
import re
import time
from collections import Counter, defaultdict, OrderedDict
from threading import Lock

from fastapi import HTTPException

from app import config
from app.database import connection, public_product
from .merchandise import (COMPLEMENTS, identity, kind, normalized, display_name,
                          purchase_context, exclude_owned, is_complement)

_cache = OrderedDict()
_cache_lock = Lock()
CATALOG_SCAN_LIMIT = 50000
MODEL_CANDIDATE_LIMIT = 320
RULE_VERSION = 'retail-context-v2'


def query_matches(product,query):
    text=normalized(display_name(product.get('name')))
    q=normalized(query)
    expected=next((types for prefix,types in (
        ('man hinh',{'monitor'}),('may tinh bang',{'tablet'}),('chuot',{'mouse'}),
        ('ban phim',{'keyboard'}),('laptop',{'laptop'}),('dien thoai',{'phone'}),
        ('cap sac',{'cable'}),('kem chong nang',{'sunscreen'}),('tai nghe',{'earbuds','headphones'})
    ) if q.startswith(prefix)),None)
    shop=normalized(product.get('shop_name',''))
    matches=all(term in text for term in q.split()) or all(term in shop for term in q.split())
    return (not expected or kind(product) in expected) and matches


def attributes(product):
    """Only title-level evidence; generated prose in parentheses is untrusted."""
    title = normalized(display_name(product.get('name')))
    tags = set()
    for tag, terms in {
        'gaming': ('gaming', 'lightsync', 'superlight'),
        'wireless': ('khong day', 'bluetooth', 'wireless', 'pebble', 'm331'),
        'ergonomic': ('cong thai hoc', 'mx master'),
        'badminton': ('cau long',), 'tennis': ('tennis',),
        'running': ('chay bo',), 'yoga': ('yoga',),
        'usb-c': ('type c', 'usb c'), 'lightning': ('lightning',),
    }.items():
        if any(t in title for t in terms): tags.add(tag)
    if 'logitech g102' in title:tags.update({'gaming','wired'})
    if 'logitech pebble m350' in title or 'logitech m331' in title:tags.update({'wireless','office'})
    if 'mx master 3s' in title:tags.update({'wireless','office','ergonomic'})
    return tags


def _catalog_ids(db):
    """Bounded streaming scan, representatives per model and price band.

    Taking the most popular 240 raw rows exhausted whole placements with color
    copies. This index has representation for every type in the bounded catalog.
    Cache stores IDs only; stock, names, prices and orders are read fresh.
    """
    key = (str(config.DB_PATH.resolve()), db.execute('SELECT MAX(id) FROM products').fetchone()[0])
    with _cache_lock:
        cached = _cache.get(key)
        if cached and time.monotonic()-cached[0] < 120:
            return cached[1]
        groups = defaultdict(dict)
        for row in db.execute('SELECT id,name,price FROM products WHERE id<=? AND stock>0 ORDER BY id', (CATALOG_SCAN_LIMIT,)):
            p = dict(row); group = groups[identity(p)]
            # Retain price coverage without letting color copies consume RAM.
            band=int(math.log2(max(1,p['price'])))
            group.setdefault(band,p['id'])
        ids = tuple(pid for group in groups.values() for pid in group.values())
        _cache[key] = (time.monotonic(), ids)
        _cache.move_to_end(key)
        while len(_cache) > 2: _cache.popitem(last=False)
        return ids


def catalog_candidates(db):
    ids = _catalog_ids(db)
    if not ids: return []
    result = []
    for start in range(0, len(ids), 400):
        batch = ids[start:start+400]
        result.extend(dict(r) for r in db.execute(f'''SELECT p.*,c.name category_name,pr.name province_name
            FROM products p LEFT JOIN categories c ON c.id=p.category_id
            LEFT JOIN provinces pr ON pr.id=p.province_id
            WHERE p.id IN ({','.join('?' for _ in batch)}) AND p.stock>0''', batch))
    return result


def order_focus(db, user_id, order_id=None):
    if not user_id: raise HTTPException(401, 'Vui lòng đăng nhập để xem gợi ý theo đơn mua.')
    if order_id:
        order = db.execute('SELECT * FROM orders WHERE id=? AND user_id=?', (order_id,user_id)).fetchone()
    else:
        order = db.execute("SELECT * FROM orders WHERE user_id=? AND order_status!='Đã hủy' ORDER BY id DESC LIMIT 1",(user_id,)).fetchone()
    if not order: raise HTTPException(404, 'Không tìm thấy đơn mua của bạn.')
    if order['order_status']=='Đã hủy': return [], dict(order)
    items=[]
    for row in db.execute('''SELECT p.*,i.product_name purchased_name,i.unit_price purchased_price
        FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.order_id=? ORDER BY i.id''',(order['id'],)):
        p=dict(row)
        p['name']=p['purchased_name'] or p['name']
        p['price']=p['purchased_price'] or p['price']
        items.append(p)
    return items, dict(order)


def _distinct(ranked, limit):
    """A shared stock photo is not a product identity."""
    seen=set();chosen=[]
    for p in ranked:
        key=identity(p)
        if key in seen: continue
        seen.add(key)
        chosen.append(p)
        if len(chosen)>=limit:break
    return chosen


def recommend(service, user_id=None, touchpoint='home', product_id=None, limit=24,
              category_id=None, *, order_id=None, write_logs=True):
    started=time.perf_counter()
    order=None;focus=[]
    with connection() as db:
        owned=purchase_context(db,user_id)
        cart=[dict(r) for r in db.execute('''SELECT p.*,ci.is_selected FROM cart_items ci
            JOIN products p ON p.id=ci.product_id WHERE ci.user_id=? ORDER BY ci.id''',(user_id,))] if user_id else []
        if touchpoint in ('orders','post_purchase'):
            focus,order=order_focus(db,user_id,order_id)
        elif touchpoint in ('similar','complementary'):
            target=db.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone()
            if not target: raise HTTPException(404,'Sản phẩm không tồn tại.')
            focus=[dict(target)]
        elif touchpoint=='cart':
            focus=[p for p in cart if p['is_selected']]
        signals=[dict(r) for r in db.execute('''SELECT p.*,h.action_type,h.id event_id
            FROM user_behavior_history h JOIN products p ON p.id=h.product_id
            WHERE h.user_id=? AND h.action_type IN ('click','favorite','add_to_cart')
            ORDER BY h.id DESC LIMIT 32''',(user_id,))] if user_id else []
        candidates=catalog_candidates(db)
    initial_count=len(candidates)
    automatic=touchpoint in ('home','deals','similar','cart','complementary','orders','post_purchase')
    candidates=exclude_owned(candidates,owned,cart if touchpoint in ('home','deals','cart') else (),home=automatic)
    after_owned=len(candidates)
    focus_keys={identity(p) for p in focus}
    candidates=[p for p in candidates if identity(p) not in focus_keys]
    context_kind=kind(focus[0]) if len(focus)==1 else None
    affinity=Counter()
    # Recent orders are stronger context than old browsing. No fabricated clicks.
    hot=[p for p in owned['items'] if p.get('hot_purchase')][:8]
    interests=hot+signals[:8]
    for index,p in enumerate(interests):
        action='purchase' if p.get('hot_purchase') else p.get('action_type','click')
        k=kind(p);weight={'purchase':5,'add_to_cart':4,'favorite':3,'click':2}[action]/(1+index*.3)
        if p.get('hot_purchase'):
            for related in COMPLEMENTS.get(k,set()): affinity[related]+=weight
        else:
            affinity[k]+=weight*1.5
            for related in COMPLEMENTS.get(k,set()): affinity[related]+=weight*.45
    broader_price=False
    if category_id is not None:
        candidates=[p for p in candidates if p['category_id']==category_id]
    if touchpoint=='similar':
        same=[p for p in candidates if kind(p)==context_kind]
        if focus[0].get('category_id') in (3,4):
            same=[p for p in same if p['category_id']==focus[0]['category_id']]
        if context_kind=='milk':
            stage=re.search(r'\bso (\d+)\b',normalized(display_name(focus[0]['name'])))
            if stage:same=[p for p in same if re.search(r'\bso '+stage[1]+r'\b',normalized(display_name(p['name'])))]
        nearby=[p for p in same if focus[0]['price']*.5<=p['price']<=focus[0]['price']*2]
        # Preserve genuinely different models; widen price only within same type.
        nearby_keys={identity(p) for p in nearby}
        wider=[p for p in same if identity(p) not in nearby_keys]
        candidates=nearby+wider if len(nearby_keys)<limit else nearby
        broader_price=bool(wider and len(nearby_keys)<limit)
    elif touchpoint in ('complementary','cart','orders','post_purchase'):
        candidates=[p for p in candidates if any(is_complement(p,f) for f in focus)] if focus else []
    elif touchpoint in ('home','deals') and interests and not category_id:
        # Exploration stays inside the customer's current merchandise needs.
        allowed=set(affinity)
        candidates=[p for p in candidates if kind(p) in allowed and (
            any(is_complement(p,f) for f in hot)
            or any(kind(p)==kind(s) or is_complement(p,s) for s in signals[:8]))]
    if touchpoint=='deals':
        candidates=[p for p in candidates if p.get('original_price',0)>p['price']]
    after_context=len(candidates)

    def context_score(p):
        if touchpoint=='similar':
            f=focus[0];a=attributes(p);b=attributes(f)
            overlap=len(a&b)/max(1,len(b))
            price_fit=math.exp(-abs(math.log(max(p['price'],1)/max(f['price'],1))))
            return .65*price_fit+.35*overlap
        if focus:
            # Same compatibility filters as recall, with relevant purpose tags.
            return max((.7+.3*len(attributes(p)&attributes(f))/max(1,len(attributes(f)))
                       for f in focus if is_complement(p,f)),default=0)
        if affinity: return affinity[kind(p)]/max(affinity.values())
        return 0.5

    candidates.sort(key=lambda p:(context_score(p),p.get('rating_star',0),p.get('sold_count',0),-p['id']),reverse=True)
    # Reserve at least one slot for every eligible model before adding variants.
    distinct=[];variants=[];seen=set()
    for p in candidates:
        key=identity(p)
        if key in seen: variants.append(p)
        else: seen.add(key);distinct.append(p)
    candidates=(distinct+variants)[:MODEL_CANDIDATE_LIMIT]
    model=service.model;scores={};similarities={};extra={};failure=None
    inference_start=time.perf_counter()
    if model and candidates:
        try:
            model.items.register_products(candidates+focus)
            mapped=[p for p in candidates if p['raw_item_id'] in model.items]
            ids=[p['raw_item_id'] for p in mapped]
            if ids and user_id:
                predicted,extra=model.predict(user_id,ids)
                if len(predicted)!=len(ids) or not all(math.isfinite(v) and 0<=v<=1 for v in predicted):
                    raise ValueError('Invalid checkpoint probabilities')
                scores=dict(zip(ids,predicted))
            if ids and focus and focus[0]['raw_item_id'] in model.items:
                values=model.similarities(focus[0]['raw_item_id'],ids)
                if len(values)!=len(ids) or not all(math.isfinite(v) for v in values):
                    raise ValueError('Invalid checkpoint similarity')
                similarities=dict(zip(ids,values))
        except Exception as exc:
            # A failure must not leave partly scored items labeled as AI.
            scores={};similarities={};failure=type(exc).__name__
    inference_ms=(time.perf_counter()-inference_start)*1000
    ranking_signal=scores or similarities
    levels=sorted(set(ranking_signal.values()))
    percentiles={value:(i/(len(levels)-1) if len(levels)>1 else .5) for i,value in enumerate(levels)}
    model_order={raw:percentiles[value] for raw,value in ranking_signal.items()}
    visible=[]
    for p in candidates:
        raw=p['raw_item_id'];p=dict(p)
        relevance=context_score(p)
        model_rank=model_order.get(raw,.5)
        quality=min(1,p.get('rating_star',0)/5)
        # Unverified semantic mapping: MUSE refines order among merchandise-
        # eligible candidates; it cannot override context/spec constraints.
        p['ranking_score']=round(.65*relevance+.30*model_rank+.05*quality,7)
        if raw in scores:p['p_click']=round(scores[raw],7)
        if raw in similarities:p['similarity']=round(similarities[raw],6)
        p['recommendation_source']='ai' if raw in scores or raw in similarities else 'catalog'
        p['recommendation_reason']='Cùng loại và nhu cầu sử dụng' if touchpoint=='similar' else 'Phù hợp với những món bạn đang quan tâm'
        p['context_relevance']=round(relevance,5)
        p['price_tier_match']=bool(focus) and .5*focus[0]['price']<=p['price']<=2*focus[0]['price']
        if touchpoint=='similar':p['similar_price_band']='nearby' if p['price_tier_match'] else 'broader'
        visible.append(public_product(p))
    visible.sort(key=lambda p:(p['ranking_score'],p.get('sold_count',0),-p['id']),reverse=True)
    if touchpoint in ('home','deals'):
        # Limit repetitive types while retaining deterministic pagination prefixes.
        counts=Counter();first=[];rest=[]
        for p in visible:
            k=kind(p)
            if counts[k]<4:first.append(p);counts[k]+=1
            else:rest.append(p)
        visible=first+rest
    all_models=_distinct(visible,len(visible));items=all_models[:limit]
    model_used=any(p['recommendation_source']=='ai' for p in items)
    meta={**extra,'touchpoint':touchpoint,'rule_version':RULE_VERSION,'engine':'Alibaba MUSE + merchandise context' if model_used else 'Catalog context',
          'strategy':'bounded model recall → ownership/spec filtering → MUSE ranking → model diversity',
          'score_type':'p_click' if scores and model_used else 'cosine_similarity' if similarities and model_used else 'catalog_relevance',
          'checkpoint_loaded':model is not None,'model_used':model_used,'candidate_count':len(candidates),
          'semantic_mapping_verified':False,'checkpoint_scores_unchanged':True,
          'context_policy':touchpoint+'_merchandise_constraints','focus_product_ids':[p['id'] for p in focus],
          'focus_names':[display_name(p['name']) for p in focus], 'order_id':order['id'] if order else None,
          'purchase_policy':{'excluded_models':len(owned['keys']),'recent_durable_types':sorted(owned['recent_kinds']),
                             'durable_cooldown_days':30,'cancelled_orders_excluded':True,'category_bypass':False},
          'retrieval':{'catalog_rows_scanned_max':CATALOG_SCAN_LIMIT,'representatives':initial_count,
                       'after_ownership':after_owned,'after_context':after_context,'eligible_models':len(all_models),
                       'requested':limit,'returned':len(items),'deduplicate_by':'model_not_photo','broader_price':broader_price},
          'has_more':len(all_models)>limit,'inference_ms':round(inference_ms,2),
          'latency_ms':round((time.perf_counter()-started)*1000,2)}
    if failure:meta['fallback_reason']='inference_failed:'+failure
    elif not model_used:meta['fallback_reason']='guest_context' if not user_id else 'model_unavailable' if not model else 'no_model_candidates'
    if not items:
        meta['empty_reason']=('cancelled_order' if order and order['order_status']=='Đã hủy' else
                              'recent_purchase_type' if touchpoint=='similar' and context_kind in owned['recent_kinds'] else 'no_eligible_merchandise')
    if user_id and write_logs:
        with service.metrics_lock:
            service.last_metrics[user_id]=meta;service.last_metrics.move_to_end(user_id)
            while len(service.last_metrics)>128:service.last_metrics.popitem(last=False)
        with connection(write=True) as db:
            db.execute('''INSERT INTO recommendation_logs(user_id,touchpoint,candidate_count,top_recommended_ids,model_name,latency_ms)
                VALUES (?,?,?,?,?,?)''',(user_id,touchpoint,len(candidates),','.join(str(p['id']) for p in items),meta['engine'],meta['latency_ms']))
    # Taobao offline AUC does not evaluate the synthetic merchandise mapping or
    # this hybrid ranker. Never attach that number as commerce accuracy.
    return {'items':items,'meta':meta,'quality':{'available':False,'reason':'illustrative_catalog_not_evaluated'}}
