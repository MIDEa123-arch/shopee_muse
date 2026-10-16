"""Reversible, idempotent metadata migration. Never edits a checkpoint or raw data.

Run with DATABASE_PATH=/path/to/copy.db .venv/bin/python -m scripts.migrate_taobao
Original IDs, features, profiles, orders, cart and real interactions are preserved.
"""
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq

from app import config
from app.database import initialize, connection
from app.native_catalog import MODE, catalog_info


def repair_orphans(db):
    """Remove obsolete test-session/log/notice rows whose user no longer exists.

    These rows are preserved in the pre-migration SQLite backup. Orders, cart,
    features and actual user interactions are deliberately excluded.
    """
    counts = {}
    for table in ('sessions','recommendation_logs','notifications'):
        count = db.execute(f'DELETE FROM {table} WHERE user_id NOT IN (SELECT id FROM users)').rowcount
        if count:
            counts[table] = count
    return counts


def migrate():
    initialize()
    with connection() as db:
        if catalog_info(db)['mode'] == MODE:
            return catalog_info(db)
        products = list(db.execute('SELECT id,raw_item_id FROM products ORDER BY id'))
        features = {r['raw_item_id']: json.loads(r['features_json'])
                    for r in db.execute('SELECT * FROM muse_item_features')}
    if not products or any(p['raw_item_id'] not in features for p in products):
        raise ValueError('Every displayed item must have original model features')
    # Read only four small columns in bounded batches. Never load embeddings here.
    wanted = {p['raw_item_id'] for p in products}
    verified = set()
    source = config.DATASET_DIR / 'raw/item_features.parquet'
    for batch in pq.ParquetFile(source).iter_batches(batch_size=32768, columns=['205','206','213','214']):
        for row in batch.to_pylist():
            raw = row['205']
            if raw in wanted:
                if any(features[raw].get(k) != row[k] for k in ('205','206','213','214')):
                    raise ValueError(f'Original feature mismatch for {raw}')
                verified.add(raw)
    # Historical sequence IDs need not occur in the released item-feature table.
    # Their original category remains usable in history; missing geography is not
    # enough evidence to treat them as fully featured recommendation targets.
    sequence_pairs = set(); profiles_by_source = {}
    with connection() as db:
        for row in db.execute('SELECT features_json,source FROM muse_user_features'):
            user = json.loads(row['features_json'])
            profiles_by_source.setdefault(row['source'],{})[user['129_1']] = user
            sequence_pairs.update(zip(user['150_2_180'],user['151_2_180']))
    profile_columns = ['129_1','130_1','130_2','130_3','130_4','130_5','150_2_180','151_2_180']
    verified_profiles = 0
    for filename, profiles in profiles_by_source.items():
        remaining = set(profiles)
        shard = config.DATASET_DIR/'test'/Path(filename).name
        for batch in pq.ParquetFile(shard).iter_batches(batch_size=16,columns=profile_columns):
            for row in batch.to_pylist():
                if row['129_1'] not in remaining:
                    continue
                if any(row[k] != profiles[row['129_1']][k] for k in profile_columns):
                    raise ValueError('User features/history differ from the original Taobao shard')
                remaining.remove(row['129_1']); verified_profiles += 1
            if not remaining:
                break
        if remaining:
            raise ValueError('A profile is missing from its recorded original Taobao shard')
    if any((raw,features[raw]['206']) not in sequence_pairs for raw in wanted-verified):
        raise ValueError('An item has neither original features nor a verified sequence/category pair')
    backup = config.DB_PATH.parent / 'backups' / ('before-native-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.db')
    backup.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.DB_PATH) as src, sqlite3.connect(backup) as dest:
        src.backup(dest)
    counts = Counter(features[raw]['206'] for raw in wanted)
    # Common groups first; tie-breaking by int64 IDs makes aliases reproducible.
    groups = {raw: 10000 + index for index, (raw, _) in enumerate(sorted(counts.items(), key=lambda x: (-x[1], x[0])), 1)}
    info = {'mode': MODE, 'source': 'Taobao-MM', 'product_count': len(verified),
            'history_catalog_count':len(products), 'history_only_count':len(wanted-verified),
            'group_count': len({features[r]['206'] for r in verified}), 'original_features_verified': len(verified),
            'original_profiles_verified':verified_profiles,
            'titles_available': False, 'photos_available': False, 'commerce_simulated': True,
            'source_url': 'https://taobao-mm.github.io/'}
    with connection(write=True) as db:
        for raw, category_id in groups.items():
            alias = category_id - 10000
            db.execute('INSERT INTO categories(id,name,slug,icon) VALUES (?,?,?,?)',
                       (category_id, f'Nhóm {alias:03d}', f'taobao-{alias:03d}', 'sparkles'))
        for p in products:
            raw = p['raw_item_id']; feature = features[raw]; category_id = groups[feature['206']]
            name = f'Mẫu TB-{p["id"]:05d}'
            description = (f'{name} thuộc Nhóm {category_id-10000:03d} trong dữ liệu Taobao-MM. '
                           'Tên gốc và ảnh gốc không được công bố. Hình học trên thẻ chỉ dùng để nhận diện mã mẫu. '
                           'Giá, tồn kho, vận chuyển và mua hàng là mô phỏng để trải nghiệm chức năng.')
            db.execute('''UPDATE products SET name=?,category_id=?,image_url=?,shop_name=?,description=?,
                is_mall=0,rating_star=0,rating_count=0,sold_count=0,discount_percent=0,original_price=price,
                catalog_source='taobao-mm',source_category_id=?,source_city_id=?,source_province_id=? WHERE id=?''',
                (name,category_id,f'/api/item-art/{p["id"]}.svg',f'Bộ sưu tập {category_id-10000:03d}',
                 description,str(feature['206']),str(feature['213']),str(feature['214']),p['id']))
            db.execute('UPDATE products SET source_feature_complete=? WHERE id=?',(int(raw in verified),p['id']))
            if raw not in verified:
                db.execute('UPDATE products SET stock=0 WHERE id=?',(p['id'],))
        # These were artificial classroom overrides, not original or real actions.
        db.execute("DELETE FROM user_behavior_history WHERE action_type='demo_interest'")
        for before,after in [('VOUCHERMUSE30K','TAOBAO30K'),('MUSEVIP100K','TAOBAOVIP100K'),('SHOPEEAI20','TAOBAOAI20')]:
            db.execute('UPDATE vouchers SET code=? WHERE code=?',(after,before))
        info['orphan_rows_repaired'] = repair_orphans(db)
        db.execute("INSERT INTO catalog_settings(key,value) VALUES ('source',?)", (json.dumps(info),))
        db.execute("INSERT OR REPLACE INTO catalog_settings(key,value) VALUES ('migration_backup',?)", (str(backup),))
    return {**info,'backup':str(backup)}


if __name__ == '__main__':
    print(json.dumps(migrate(), ensure_ascii=False, indent=2))
