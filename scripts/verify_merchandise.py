"""Read-only audit of the actual catalog/checkpoint, with bounded candidate pools.

Run under a memory limit, with other model test processes stopped.
python -m scripts.verify_merchandise --output docs/merchandise_verification.json
No orders, accounts, carts or behavior rows are created or changed.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.database import connection
from app.recommender.service import service
from app.recommender.commerce import personalized_deals
from app.recommender.merchandise import identity, kind, purchase_context, is_complement


def summary(result):
    return {'count':len(result['items']),'model_used':result['meta']['model_used'],
            'score_type':result['meta']['score_type'],
            'purchase_policy':result['meta'].get('purchase_policy'),
            'post_purchase_accessories':result['meta'].get('post_purchase_accessories'),
            'items':[{k:p[k] for k in ('id','name','price','p_click','similarity','image_url') if k in p}
                     for p in result['items'][:6]]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    service.load()
    if not service.model:raise SystemExit(f'Checkpoint unavailable: {service.error}')
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'read_only':True,
            'checkpoint_ready':True,'checks':[],'examples':{}}

    def check(label,passed,**details):
        report['checks'].append({'check':label,'passed':bool(passed),**details})

    with connection() as db:
        counts_before={t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in
                       ('orders','order_items','cart_items','users','user_behavior_history','recommendation_logs')}
    for uid in (1,2):
        with connection() as db:owned=purchase_context(db,uid)
        home=service.recommend(uid,limit=24,write_logs=False)
        check(f'user_{uid}_home_excludes_owned_model',bool(home['items']) and all(identity(p) not in owned['keys'] for p in home['items']))
        check(f'user_{uid}_home_cools_down_recent_durable_type',all(kind(p) not in owned['recent_kinds'] for p in home['items']))
        check(f'user_{uid}_home_unique_models',len(home['items'])==len({identity(p) for p in home['items']}))
        check(f'user_{uid}_home_unique_photos',len(home['items'])==len({p['image_url'] for p in home['items']}))
        with connection() as db:deals=personalized_deals(db,uid,6)
        check(f'user_{uid}_deals_excludes_owned_models',bool(deals['items']) and all(identity(p) not in owned['keys'] for p in deals['items']))
        report['examples'][f'user_{uid}_home']=summary(home)

    for focus_id in (17438,20739,17150):
        with connection() as db:
            row=db.execute('SELECT * FROM products WHERE id=?',(focus_id,)).fetchone()
            if not row:continue
            focus=dict(row)
        similar=service.recommend(None,'similar',focus_id,6,write_logs=False)
        check(f'{focus_id}_similar_is_other_model_same_type_in_price_band',bool(similar['items']) and all(
            identity(p)!=identity(focus) and kind(p)==kind(focus) and
            focus['price']*.5<=p['price']<=focus['price']*2 for p in similar['items']),count=len(similar['items']))
        comp=service.recommend(None,'complementary',focus_id,6,write_logs=False)
        check(f'{focus_id}_addons_match_merchandise_and_basic_compatibility',bool(comp['items']) and all(is_complement(p,focus) for p in comp['items']),count=len(comp['items']))
        report['examples'][f'{focus_id}_similar']=summary(similar)
        report['examples'][f'{focus_id}_addons']=summary(comp)

    with connection() as db:
        counts_after={t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in counts_before}
    check('application_row_counts_unchanged',counts_before==counts_after)
    report['passed']=sum(c['passed'] for c in report['checks'])
    report['failed']=len(report['checks'])-report['passed']
    data=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(data)
    print(json.dumps({k:report[k] for k in ('checkpoint_ready','read_only','passed','failed')},ensure_ascii=False))
    for label,result in report['examples'].items():
        print(json.dumps({'case':label,'count':result['count'],'items':[p['name'] for p in result['items'][:3]]},ensure_ascii=False))
    if report['failed']:raise SystemExit(1)


if __name__=='__main__':main()
