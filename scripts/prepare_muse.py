"""Import genuine features and full demo histories without resetting commerce data."""
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import config
from app.database import connection,initialize


def prepare():
    import pyarrow.parquet as pq
    initialize()
    with connection() as db:
        products={r['raw_item_id'] for r in db.execute('SELECT raw_item_id FROM products')}
        users={r['raw_user_id']:r['id'] for r in db.execute('SELECT id,raw_user_id FROM users WHERE raw_user_id IS NOT NULL')}
        imported={r['user_id'] for r in db.execute('SELECT user_id FROM muse_user_features')}
        known={r['raw_item_id'] for r in db.execute('SELECT raw_item_id FROM muse_item_features')}
    missing=products-known
    if missing:
        source=config.DATASET_DIR/'raw/item_features.parquet'
        for batch in pq.ParquetFile(source).iter_batches(batch_size=65536):
            rows=[r for r in batch.to_pylist() if r['205'] in missing]
            with connection(write=True) as db:
                for r in rows:
                    db.execute('INSERT OR REPLACE INTO muse_item_features VALUES (?,?)',(r['205'],json.dumps(r)))
                    missing.discard(r['205'])
            if not missing:
                break
        if missing:
            raise RuntimeError(f'Missing source features for {len(missing)} catalog products')
    wanted=set(users.values())-imported
    if wanted:
        source=config.DATASET_DIR/'test/test-shard-000000.parquet'
        for batch in pq.ParquetFile(source).iter_batches(batch_size=100):
            for row in batch.to_pylist():
                uid=users.get(row['129_1'])
                if uid not in wanted:
                    continue
                with connection(write=True) as db:
                    db.execute('INSERT INTO muse_user_features VALUES (?,?,?)',(uid,json.dumps(row),str(source.name)))
                    # Old bootstrap history used only first 40 entries; retain real live events.
                    db.execute("DELETE FROM user_behavior_history WHERE user_id=? AND product_id IS NULL AND action_type='click'",(uid,))
                    catalog={r['raw_item_id']:r['id'] for r in db.execute('SELECT id,raw_item_id FROM products')}
                    db.executemany('''INSERT INTO user_behavior_history(user_id,raw_user_id,product_id,raw_item_id,action_type)
                        VALUES (?,?,?,?,'imported_click')''',[(uid,row['129_1'],catalog.get(raw),raw) for raw in row['150_2_180'][-1000:] if raw])
                wanted.remove(uid)
            if not wanted:
                break
        if wanted:
            raise RuntimeError('Some demo users were not found in source shard')
    with connection() as db:
        print(json.dumps({'item_features':db.execute('SELECT COUNT(*) FROM muse_item_features').fetchone()[0],
                          'user_features':db.execute('SELECT COUNT(*) FROM muse_user_features').fetchone()[0],
                          'histories':[dict(r) for r in db.execute('SELECT user_id,COUNT(*) count FROM user_behavior_history GROUP BY user_id')]},ensure_ascii=False))


if __name__=='__main__':
    prepare()
