"""Balanced authentic candidates, streamed from source; no model training.

Keep all existing IDs and real interactions. Fill small original groups first,
then extend groups frequent in the original eight histories. Deterministic
reservoir sampling avoids taking a contiguous prefix of the source file.
"""
import hashlib
import heapq
import json
import mmap
import sqlite3
from collections import Counter
from datetime import datetime

import numpy as np
import pyarrow.parquet as pq

from app import config
from app.database import connection, initialize
from app.native_catalog import MODE, catalog_info

TARGET = 8192


def mapped(path):
    array=np.load(path,mmap_mode='r')
    if hasattr(array._mmap,'madvise'):
        array._mmap.madvise(mmap.MADV_RANDOM)
    return array


def contains(keys,values):
    a=np.asarray(values,dtype=np.int64);positions=np.searchsorted(keys,a)
    return (positions<len(keys)) & (keys[np.minimum(positions,len(keys)-1)]==a)


def expand(target=TARGET):
    initialize()
    with connection() as db:
        info=catalog_info(db)
        if info['mode']!=MODE:
            raise ValueError('Run migrate_taobao first')
        existing={r['raw_item_id']:dict(r) for r in db.execute('SELECT * FROM products')}
        active=Counter(p['category_id'] for p in existing.values() if p['source_feature_complete'])
        group_ids={int(p['source_category_id']):p['category_id'] for p in existing.values()}
        frequency=Counter()
        for row in db.execute('SELECT features_json FROM muse_user_features'):
            u=json.loads(row[0]);frequency.update(x for x in u['151_2_180'] if x)
        if sum(active.values())>=target and info.get('expansion_version')==1:
            return info
    popular=set(raw for raw,_ in frequency.most_common(32))
    capacities={raw:max(8-active.get(cid,0),0)+(96 if raw in popular else 0) for raw,cid in group_ids.items()}
    reservoirs={raw:[] for raw in group_ids};source=config.DATASET_DIR/'raw/item_features.parquet'
    seen=0
    for batch in pq.ParquetFile(source).iter_batches(batch_size=32768,columns=['205','206','213','214'],use_threads=False):
        for row in batch.to_pylist():
            raw=row['205'];group=row['206'];capacity=capacities.get(group,0)
            if not capacity or raw in existing:
                continue
            # Stable mixing of anonymized IDs, independent of Python hash seed.
            priority=int.from_bytes(hashlib.blake2b(str(raw).encode(),digest_size=8).digest(),'big')
            bucket=reservoirs[group]
            entry=(-priority,raw,row)
            if len(bucket)<capacity:
                heapq.heappush(bucket,entry)
            elif entry>bucket[0]:
                heapq.heapreplace(bucket,entry)
            seen+=1
    candidates={raw:[entry[2] for entry in sorted(bucket,reverse=True)] for raw,bucket in reservoirs.items()}
    # Only publish IDs actually represented by the frozen checkpoint and SCL table.
    maps=config.DATASET_DIR/'feature_map'
    item_keys=mapped(maps/'150_2_180_sorted_map_p90.npy')
    scl_keys=mapped(maps/'scl_emb_int8_p90_keys.npy')
    flat=[r for rows in candidates.values() for r in rows]
    ids=[r['205'] for r in flat];valid=contains(item_keys,ids)&contains(scl_keys,ids)
    good={r['205'] for r,ok in zip(flat,valid) if ok}
    for raw in candidates:
        candidates[raw]=[r for r in candidates[raw] if r['205'] in good]
    selected=[];counts=active.copy();offsets=Counter()
    # Fair round-robin coverage first, including groups previously absent from candidates.
    for level in range(1,9):
        for raw,cid in sorted(group_ids.items(),key=lambda x:x[1]):
            if sum(active.values())+len(selected)>=target:
                break
            if counts[cid]<level and offsets[raw]<len(candidates[raw]):
                selected.append(candidates[raw][offsets[raw]]);offsets[raw]+=1;counts[cid]+=1
    # Any remaining slots go to frequent history groups, without discarding other groups.
    while sum(active.values())+len(selected)<target:
        added=0
        for raw,_ in frequency.most_common():
            if sum(active.values())+len(selected)>=target:
                break
            if offsets[raw]<len(candidates.get(raw,[])):
                selected.append(candidates[raw][offsets[raw]]);offsets[raw]+=1;counts[group_ids[raw]]+=1;added+=1
        if not added:
            break
    backup=config.DB_PATH.parent/'backups'/('before-expand-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.db')
    backup.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(config.DB_PATH) as src,sqlite3.connect(backup) as dest:
        src.backup(dest)
    with connection(write=True) as db:
        next_id=db.execute('SELECT COALESCE(MAX(id),0)+1 FROM products').fetchone()[0]
        for row in selected:
            pid=next_id;next_id+=1;cid=group_ids[row['206']];alias=cid-10000
            price=100000+(abs(row['205'])%9)*25000
            db.execute('''INSERT INTO products(id,raw_item_id,name,category_id,price,original_price,
                discount_percent,stock,sold_count,rating_star,rating_count,image_url,province_id,shop_name,
                is_mall,is_freeship,description,catalog_source,source_feature_complete,source_category_id,
                source_city_id,source_province_id) VALUES (?,?,?,?,?,?,0,100,0,0,0,?,1,?,0,1,?,'taobao-mm',1,?,?,?)''',
                (pid,row['205'],f'Mẫu TB-{pid:05d}',cid,price,price,f'/api/item-art/{pid}.svg',
                 f'Bộ sưu tập {alias:03d}',
                 f'Mẫu Taobao-MM ẩn danh, Nhóm {alias:03d}. Hình nhận diện theo ID. Giá và mua hàng là mô phỏng.',
                 str(row['206']),str(row['213']),str(row['214'])))
            db.execute('INSERT INTO muse_item_features(raw_item_id,features_json) VALUES (?,?)',(row['205'],json.dumps(row)))
        total=db.execute('SELECT COUNT(*) FROM products WHERE source_feature_complete=1').fetchone()[0]
        groups=db.execute('SELECT COUNT(DISTINCT category_id) FROM products WHERE source_feature_complete=1').fetchone()[0]
        info.update(product_count=total,original_features_verified=total,group_count=groups,
                    history_catalog_count=db.execute('SELECT COUNT(*) FROM products').fetchone()[0],
                    expansion_version=1,expansion_added=len(selected),
                    expansion_policy='balanced_original_groups_with_checkpoint_and_scl_coverage')
        db.execute("UPDATE catalog_settings SET value=? WHERE key='source'",(json.dumps(info),))
        db.execute("INSERT OR REPLACE INTO catalog_settings(key,value) VALUES ('expansion_backup',?)",(str(backup),))
    return {**info,'backup':str(backup),'source_rows_considered':seen}


if __name__=='__main__':
    print(json.dumps(expand(),ensure_ascii=False,indent=2))
