"""Read-only real-checkpoint audit of every retail placement and product type.

Never copies the main DB, creates orders or changes behavior/logs. Run one
model process at a time under MemoryMax. Reports are functional coverage,
not estimates of customer relevance/CTR or checkpoint accuracy.
"""
import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.database import connection
from app.recommender.service import service
from app.recommender.retail import catalog_candidates, order_focus
from app.recommender.merchandise import identity, kind, purchase_context, normalized
from app.recommender.commerce import personalized_deals, complementary_bundle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('docs/retail_audit.json'))
    args=parser.parse_args()
    service.load()
    if service.model is None:raise SystemExit('Actual checkpoint unavailable: '+str(service.error))
    checks=[];examples={};coverage=[]
    def check(label,passed,**details):checks.append({'check':label,'passed':bool(passed),**details})
    def record(label,result):
        examples[label]={'count':len(result['items']),'meta':result['meta'],
                         'items':[{k:p[k] for k in ('id','name','price','image_url','p_click','similarity','ranking_score') if k in p} for p in result['items']]}
    with connection() as db:
        before={t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('users','orders','order_items','cart_items','user_behavior_history','recommendation_logs')}
        candidates=catalog_candidates(db)
        by_type=defaultdict(dict)
        for p in candidates:by_type[kind(p)].setdefault(identity(p),p)
        orders=[dict(r) for r in db.execute("SELECT id,user_id,order_status FROM orders ORDER BY id DESC LIMIT 100")]
    for uid in (1,2,22):
        with connection() as db:owned=purchase_context(db,uid)
        for tp in ('home','deals'):
            result=service.recommend(uid,tp,limit=24,write_logs=False)
            check(f'{uid}_{tp}_excludes_owned_models_and_recent_types',
                  all(identity(p) not in owned['keys'] and kind(p) not in owned['recent_kinds'] for p in result['items']),count=len(result['items']))
            check(f'{uid}_{tp}_distinct_models',len(result['items'])==len({identity(p) for p in result['items']}))
            check(f'{uid}_{tp}_checkpoint_actually_used',bool(result['items']) and result['meta']['model_used'])
            record(f'user_{uid}_{tp}',result)
            scored=[p for p in result['items'] if 'p_click' in p]
            if scored:
                values,_=service.model.predict(uid,[int(p['raw_item_id']) for p in scored])
                check(f'{uid}_{tp}_raw_prediction_values_preserved',all(abs(v-p['p_click'])<=.000000051 for v,p in zip(values,scored)))
        filtered=service.recommend(uid,'home',category_id=1,write_logs=False)
        check(f'{uid}_category_tab_cannot_bypass_recent_purchase',all(kind(p) not in owned['recent_kinds'] for p in filtered['items']))
        for purchased in owned['items']:
            if kind(purchased)=='laptop' and purchased.get('recent_purchase'):
                similar=service.recommend(uid,'similar',purchased['id'],write_logs=False)
                check(f'{uid}_purchased_laptop_detail_does_not_resell_laptops',not similar['items'])
                break
        with connection() as db:
            deals=personalized_deals(db,uid,6)
            bundle=complementary_bundle(db,uid)
        check(f'{uid}_deals_wrapper_shares_rules',deals['meta']['rule_version']=='retail-context-v2')
        if bundle.get('items'):check(f'{uid}_bundle_wrapper_shares_rules',bundle['meta']['rule_version']=='retail-context-v2')
    # Independent explicit product-type expectations, not the eligibility helper.
    # These IDs are existing real catalog examples and orders; no data is created.
    for order in orders:
        uid=order['user_id'];oid=order['id']
        result=service.recommend(uid,'orders',order_id=oid,limit=12,write_logs=False)
        with connection() as db:focus,_=order_focus(db,uid,oid)
        check(f'order_{oid}_uses_all_its_items',set(result['meta']['focus_product_ids'])=={p['id'] for p in focus})
        if order['order_status']=='Đã hủy':
            check(f'order_{oid}_cancelled_has_no_recommendations',not result['items']);continue
        if focus and all('cau long' in normalized(p['name']) for p in focus):
            allowed=('bao vot','binh giu nhiet','giay the thao','giay chay bo','giay sneaker','qua cau long')
            check(f'order_{oid}_badminton_has_no_electronics',len(result['items'])>=6 and all(normalized(p['name']).startswith(allowed) for p in result['items']))
            record(f'order_{oid}_badminton',result)
        if focus and all(normalized(p['name']).startswith('giay') for p in focus):
            allowed=('binh giu nhiet','lot giay','bo ve sinh giay','day giay','vien khu mui giay','tui dung giay','khan lau giay','vo ','tat ')
            check(f'order_{oid}_footwear_has_six_related_accessories_and_no_electronics',len(result['items'])>=6 and all(normalized(p['name']).startswith(allowed) for p in result['items']))
            record(f'order_{oid}_footwear',result)
        if focus and all(normalized(p['name']).startswith('laptop') for p in focus):
            allowed=('chuot','ban phim','man hinh','cu sac','balo laptop','tai nghe')
            check(f'order_{oid}_laptop_only_actual_accessory_types',bool(result['items']) and all(normalized(p['name']).startswith(allowed) for p in result['items']))
            record(f'order_{oid}_laptop',result)
        after=service.recommend(uid,'post_purchase',order_id=oid,limit=12,write_logs=False)
        check(f'order_{oid}_success_and_order_placements_agree',[p['id'] for p in result['items']]==[p['id'] for p in after['items']])
    # Every type is exercised, including types with only one model. Shortages
    # are recorded explicitly instead of being passed off as model precision.
    for label,models in sorted(by_type.items()):
        focus=next(iter(models.values()))
        similar=service.recommend(None,'similar',focus['id'],6,write_logs=False)
        complement=service.recommend(None,'complementary',focus['id'],6,write_logs=False)
        check(f'{label}_similar_never_changes_product_type',all(kind(p)==label and identity(p)!=identity(focus) for p in similar['items']))
        check(f'{label}_similar_has_distinct_models',len(similar['items'])==len({identity(p) for p in similar['items']}))
        check(f'{label}_similar_has_no_broken_asset_paths',all((Path(__file__).resolve().parents[1]/p['image_url'].lstrip('/')).is_file() for p in similar['items']))
        coverage.append({'kind':label,'catalog_models':len(models),'similar_count':len(similar['items']),
                         'addons_count':len(complement['items']),'focus_id':focus['id']})
        if label=='mouse':
            check('mouse_alternatives_not_limited_by_stock_photos',len(models)>=4 and len(similar['items'])>=min(6,len(models)-1))
            check('mouse_results_are_named_mice',all(normalized(p['name']).startswith('chuot') for p in similar['items']))
            record('mouse_detail',similar);record('mouse_addons',complement)
    with connection() as db:
        after={t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in before}
    check('no_customers_orders_carts_history_or_log_rows_changed',before==after)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'read_only':True,'checkpoint_ready':True,
            'semantic_mapping_verified':False,'passed':sum(c['passed'] for c in checks),
            'failed':sum(not c['passed'] for c in checks),'checks':checks,'coverage':coverage,'examples':examples,
            'limits':['Functional constraints, not customer relevance accuracy.','Generated Vietnamese labels are not verified Taobao metadata.',
                      'At most 50,000 raw catalog rows and 320 scored candidates per request.','No training and no production order/cart mutations.']}
    args.output.parent.mkdir(exist_ok=True,parents=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','failed','checkpoint_ready','read_only')},ensure_ascii=False))
    print(json.dumps({'coverage':coverage},ensure_ascii=False))
    if report['failed']:
        print(json.dumps([c for c in checks if not c['passed']],ensure_ascii=False));raise SystemExit(1)


if __name__=='__main__':main()
