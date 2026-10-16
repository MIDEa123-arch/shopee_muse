"""Replace unreferenced duplicate demo rows with a small curated assortment.

No raw IDs, original feature fields, checkpoint, orders or behavior are edited.
Names/photos remain an explicitly unverified presentation of Taobao IDs.
Only --apply writes; saves complete before-images of affected product rows.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.database import connection
from app.native_catalog import catalog_info
from app.recommender.merchandise import identity, kind

MANIFEST=config.ROOT/'app/recommender/curated_retail.json'


def install(db,entries,backup_dir,apply=False):
    if catalog_info(db)['mode'] not in ('vietnam_tiki_v1','amazon_reviews_2023_v1'):
        raise ValueError('Curated enrichment only supports the illustrative retail catalog')
    protected=set()
    for table in ('order_items','cart_items','wishlist','reviews','user_behavior_history'):
        protected.update(r[0] for r in db.execute(f'SELECT DISTINCT product_id FROM {table}') if r[0] is not None)
    protected.update(r[0] for r in db.execute('''SELECT p.id FROM user_behavior_history h
        JOIN products p ON p.raw_item_id=h.raw_item_id'''))
    for row in db.execute('SELECT top_recommended_ids FROM recommendation_logs ORDER BY id DESC LIMIT 500'):
        protected.update(int(x) for x in (row[0] or '').split(',') if x.strip().isdigit())
    rows=[dict(r) for r in db.execute('SELECT * FROM products WHERE id<=50000 ORDER BY id')]
    counts=Counter(identity(p) for p in rows)
    anchors={}
    for p in rows:anchors.setdefault(identity(p),p['id'])
    available=[p for p in reversed(rows) if p['id'] not in protected
               and p.get('catalog_source')!='retail-curated'
               and counts[identity(p)]>1 and anchors[identity(p)]!=p['id']]
    used=set();plan=[]
    for entry in entries:
        if db.execute("SELECT 1 FROM products WHERE name=? AND catalog_source='retail-curated'",(entry['name'],)).fetchone():continue
        if not (config.ROOT/entry['image_url'].lstrip('/')).is_file():raise ValueError('Missing image: '+entry['image_url'])
        row=next((p for p in available if p['id'] not in used and kind(p)==entry['prototype_kind']),None)
        if row is None:raise ValueError('No unused duplicate for '+entry['key'])
        used.add(row['id']);plan.append((row,entry))
    if not apply or not plan:return {'planned':len(plan),'applied':0,'ids':[p['id'] for p,e in plan]}
    backup_dir=Path(backup_dir);backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/('retail-curation-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.json')
    backup.write_text(json.dumps({'version':1,'products_before':[p for p,e in plan]},ensure_ascii=False,indent=2)+'\n')
    columns={r[1] for r in db.execute('PRAGMA table_info(products)')}
    mapping=[]
    for old,entry in plan:
        changes={'name':entry['name'],'price':entry['price'],'original_price':entry['price'],
                 'category_id':entry['category_id'],'image_url':entry['image_url'],
                 'description':entry['description'],'discount_percent':0,'stock':50,'sold_count':0,
                 'rating_star':0,'rating_count':0,'is_mall':0,'is_freeship':1,
                 'shop_name':'Gian hàng trải nghiệm','brand':entry['brand'],
                 'images_json':json.dumps([entry['image_url']]),'catalog_source':'retail-curated'}
        changes={k:v for k,v in changes.items() if k in columns}
        db.execute('UPDATE products SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',(*changes.values(),old['id']))
        mapping.append({'key':entry['key'],'product_id':old['id'],'raw_item_id':str(old['raw_item_id']),
                        'source_url':entry['source_url'],'semantic_mapping_verified':False})
    db.execute("INSERT OR REPLACE INTO catalog_settings(key,value) VALUES ('retail_curated',?)",(json.dumps({'version':1,'mapping':mapping,'backup':str(backup)},ensure_ascii=False),))
    from app.recommender import retail
    with retail._cache_lock:retail._cache.clear()
    return {'planned':len(plan),'applied':len(plan),'backup':str(backup),'ids':[p['id'] for p,e in plan]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();entries=json.loads(MANIFEST.read_text())['products']
    with connection(write=args.apply) as db:
        print(json.dumps(install(db,entries,config.ROOT/'data/backups',args.apply),ensure_ascii=False))


if __name__=='__main__':main()
