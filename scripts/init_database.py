"""Idempotent demo bootstrap. Existing commerce records are always preserved."""
import json
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import config
from app.database import connection,initialize
from app.security import hash_password
from app.seed_data import CATEGORIES,PRODUCT_TEMPLATES,SAMPLE_PROFILES,SHOPS,VN_ADMIN_UNITS,VOUCHERS


def initialize_demo():
    if not config.DEMO_MODE:
        raise SystemExit('Demo seed is disabled when DEMO_MODE=false. Use migrations and real merchant data.')
    initialize()
    with connection() as db:
        if db.execute('SELECT COUNT(*) FROM products').fetchone()[0]:
            print('Database already has products. Existing data preserved:',config.DB_PATH)
            return
    rng=random.Random(42)
    item_file=config.DATASET_DIR/'raw/item_features.parquet'
    test_file=config.DATASET_DIR/'test/test-shard-000000.parquet'
    genuine=item_file.exists() and test_file.exists()
    if genuine:
        import pyarrow.parquet as pq
        items=next(pq.ParquetFile(item_file).iter_batches(batch_size=1000)).to_pylist()
        profiles=next(pq.ParquetFile(test_file).iter_batches(batch_size=100)).to_pylist()
    else:
        items=[{'205':-10_000_000-i} for i in range(1000)]
        profiles=[{'129_1':-9_000_000-i} for i in range(8)]
    password_hash=hash_password('Demo12345!')
    source_map_path=config.ROOT/'static/images/catalog/sources.json'
    source_map=json.loads(source_map_path.read_text()) if source_map_path.exists() else {}
    with connection(write=True) as db:
        for i,unit in enumerate(VN_ADMIN_UNITS,1):
            if unit[0]=='Bình Dương':
                unit=('Hưng Yên','Tỉnh','Miền Bắc',22000)
            db.execute('INSERT OR IGNORE INTO provinces(id,name,type,region,shipping_base_fee) VALUES (?,?,?,?,?)',(i,*unit))
        for i,c in enumerate(CATEGORIES,1):
            db.execute('INSERT OR IGNORE INTO categories(id,name,slug,icon) VALUES (?,?,?,?)',(i,*c))
        for v in VOUCHERS:
            db.execute('INSERT OR IGNORE INTO vouchers(code,title,description,discount_type,discount_value,min_order_value,max_discount_amount) VALUES (?,?,?,?,?,?,?)',v)
        for i,item in enumerate(items):
            cat=i%8+1;templates=PRODUCT_TEMPLATES[cat];template=templates[(i//8)%len(templates)]
            variant=i//8//len(templates)+1;delta=(variant*5000)%30000
            name,price,original,image=template;shop,province=SHOPS[cat-1]
            db.execute('''INSERT INTO products(raw_item_id,name,category_id,price,original_price,discount_percent,stock,
                sold_count,rating_star,rating_count,image_url,province_id,shop_name) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (item['205'],f'{name} (Model #{variant})',cat,price+delta,original+delta,round((original-price)/(original+delta)*100),
                 rng.randint(50,300),rng.randint(150,6500),round(rng.uniform(4.7,5),1),rng.randint(50,1500),source_map.get(image.split('?')[0],image),province,shop))
        seen=set();index=0
        for row in profiles:
            raw_uid=row['129_1']
            if raw_uid in seen:
                continue
            seen.add(raw_uid);p=SAMPLE_PROFILES[index]
            name,email,phone,avatar,gender,year,province,address,tier,coins,wallet=p
            uid=db.execute('''INSERT OR IGNORE INTO users(raw_user_id,full_name,email,phone,password_hash,avatar_url,gender,birth_year,
                province_id,address_detail,member_tier,shopee_coins,wallet_balance) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (raw_uid,name,email,phone,password_hash,source_map.get(avatar.split('?')[0],avatar),gender,year,province,address,tier,coins,wallet)).lastrowid
            if uid:
                for voucher_id in (1,2):
                    db.execute('INSERT OR IGNORE INTO user_vouchers(user_id,voucher_id) VALUES (?,?)',(uid,voucher_id))
                db.execute("INSERT INTO notifications(user_id,title,content,type) VALUES (?,'Chào mừng bạn!','Khám phá các sản phẩm dành riêng cho bạn.','system')",(uid,))
            index+=1
            if index==8:
                break
    initialize()
    print(json.dumps({'database':str(config.DB_PATH),'catalog_ids':'Taobao-MM' if genuine else 'synthetic demo — MUSE unavailable',
                      'demo_password':'Demo12345!','users':index,'products':len(items)},ensure_ascii=False))
    if genuine:
        from scripts.prepare_muse import prepare
        prepare()


if __name__=='__main__':
    initialize_demo()
