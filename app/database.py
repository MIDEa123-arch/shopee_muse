import sqlite3
import json
import re
from contextlib import contextmanager
from pathlib import Path

from app import config


@contextmanager
def connection(write=False):
    db = sqlite3.connect(str(config.DB_PATH), timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 15000")
    try:
        if write:
            db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript((Path(__file__).parent / "schema.sql").read_text())
        db.executescript("""
        CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS catalog_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS product_presentations (
          product_id INTEGER PRIMARY KEY REFERENCES products(id),name TEXT NOT NULL,
          category_slug TEXT NOT NULL,category_name TEXT NOT NULL,image_url TEXT NOT NULL,
          images_json TEXT NOT NULL,brand TEXT NOT NULL,description TEXT NOT NULL,
          price INTEGER NOT NULL,original_price INTEGER NOT NULL,shop_name TEXT NOT NULL,
          template_id INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS presentation_category ON product_presentations(category_slug);
        CREATE TABLE IF NOT EXISTS addresses (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          recipient_name TEXT NOT NULL, phone TEXT NOT NULL, province_id INTEGER NOT NULL REFERENCES provinces(id),
          detail TEXT NOT NULL, label TEXT NOT NULL DEFAULT 'Nhà riêng', is_default INTEGER NOT NULL DEFAULT 0);
        CREATE UNIQUE INDEX IF NOT EXISTS one_default_address ON addresses(user_id) WHERE is_default=1;
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS reset_challenges (
          id TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), code_hash TEXT NOT NULL,
          expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS auth_attempts (key TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS auth_attempt_key ON auth_attempts(key,created_at);
        CREATE TABLE IF NOT EXISTS wishlist (
          user_id INTEGER NOT NULL REFERENCES users(id), product_id INTEGER NOT NULL REFERENCES products(id),
          PRIMARY KEY(user_id,product_id));
        CREATE TABLE IF NOT EXISTS reviews (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          product_id INTEGER NOT NULL REFERENCES products(id), rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
          content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,product_id));
        CREATE TABLE IF NOT EXISTS muse_user_features (
          user_id INTEGER PRIMARY KEY REFERENCES users(id), features_json TEXT NOT NULL, source TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS muse_item_features (
          raw_item_id INTEGER PRIMARY KEY, features_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_events (
          id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), action TEXT NOT NULL,
          entity_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS history_user_recent ON user_behavior_history(user_id,id DESC);
        CREATE INDEX IF NOT EXISTS products_category_price ON products(category_id,price);
        CREATE INDEX IF NOT EXISTS orders_user_time ON orders(user_id,id DESC);
        CREATE INDEX IF NOT EXISTS notifications_user ON notifications(user_id,is_read);
        CREATE UNIQUE INDEX IF NOT EXISTS cart_user_product ON cart_items(user_id,product_id);
        CREATE UNIQUE INDEX IF NOT EXISTS voucher_user_unique ON user_vouchers(user_id,voucher_id);
        """)
        columns = {r['name'] for r in db.execute("PRAGMA table_info(orders)")}
        product_columns = {r['name'] for r in db.execute("PRAGMA table_info(products)")}
        for name, definition in {'catalog_source': 'TEXT', 'source_feature_complete':'INTEGER', 'source_category_id': 'TEXT',
                                 'source_city_id': 'TEXT', 'source_province_id': 'TEXT'}.items():
            if name not in product_columns:
                db.execute(f'ALTER TABLE products ADD COLUMN {name} {definition}')
        for name, definition in {
            "idempotency_key": "TEXT", "request_hash": "TEXT", "voucher_id": "INTEGER",
            "shipping_discount": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if name not in columns:
                db.execute(f"ALTER TABLE orders ADD COLUMN {name} {definition}")
        for name, definition in {"product_name": "TEXT", "image_url": "TEXT", "shop_name": "TEXT"}.items():
            if name not in {r['name'] for r in db.execute("PRAGMA table_info(order_items)")}:
                db.execute(f"ALTER TABLE order_items ADD COLUMN {name} {definition}")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS order_idempotency ON orders(user_id,idempotency_key)")
        # Preserve old foreign keys when correcting the obsolete province entry.
        old = db.execute("SELECT id FROM provinces WHERE name='Bình Dương'").fetchone()
        if old:
            for table in ("users", "products", "addresses"):
                db.execute(f"UPDATE {table} SET province_id=2 WHERE province_id=?", (old['id'],))
            db.execute("UPDATE provinces SET name='Hưng Yên',region='Miền Bắc',shipping_base_fee=22000 WHERE id=?", (old['id'],))
        db.execute("""INSERT INTO addresses(user_id,recipient_name,phone,province_id,detail,is_default)
          SELECT u.id,u.full_name,u.phone,u.province_id,u.address_detail,1 FROM users u
          WHERE u.province_id IS NOT NULL AND u.address_detail IS NOT NULL
          AND NOT EXISTS(SELECT 1 FROM addresses a WHERE a.user_id=u.id)""")
        db.execute("INSERT OR IGNORE INTO schema_migrations VALUES (1)")
        # Historical anonymous-card clicks must not be reinterpreted as interest
        # in the newly attached merchandise. Begin context evidence at rollout.
        if db.execute('SELECT 1 FROM product_presentations LIMIT 1').fetchone():
            boundary=db.execute('SELECT COALESCE(MAX(id),0) FROM user_behavior_history').fetchone()[0]
            db.execute("INSERT OR IGNORE INTO catalog_settings VALUES ('storefront_context',?)",
                       (json.dumps({'version':1,'after_behavior_id':boundary}),))


VERIFIED_CATEGORY_IMAGES = {
    1: [
        '/static/images/storefront/78.webp', '/static/images/storefront/79.webp', '/static/images/storefront/80.webp',
        '/static/images/storefront/81.webp', '/static/images/storefront/82.webp', '/static/images/catalog/deb5000b89dc7274.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/e3/a7/5a/bc0d48d4659e0d2bb24b9920e737a018.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/29/d3/ff/c375a5143579ff61d25375e3e55f5a2a.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/bf/0e/a9/62280749cd095d6dd351c8e01d2b7365.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/6d/fc/25/42afb0c0cf52cf8f83a0f98d5e550ff7.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/3c/e0/00/bccd602b77761cbfabe803ff1ee94ebc.png'
    ],
    2: [
        '/static/images/storefront/99.webp', '/static/images/storefront/100.webp', '/static/images/storefront/101.webp',
        '/static/images/storefront/102.webp', '/static/images/storefront/103.webp', '/static/images/storefront/104.webp',
        '/static/images/storefront/105.webp', '/static/images/storefront/106.webp', '/static/images/storefront/107.webp',
        '/static/images/storefront/108.webp', '/static/images/storefront/109.webp', '/static/images/storefront/110.webp',
        '/static/images/storefront/111.webp', '/static/images/storefront/112.webp',
        '/static/images/catalog/0ff14790a138c6fd.jpg', '/static/images/catalog/50867512f65f1c41.jpg',
        '/static/images/catalog/c366d5473a83e25f.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/04/1e/99/b9c26723ba7decb415260d0a29738747.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/a8/b4/d2/44b79741ec6b69a10b00782a9b750955.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/37/cd/19/02c6d6c12555558121bd0b62369bfdd2.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/68/a4/28/c0d46b9578a8bcb9f92a0247fe271298.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/91/f6/0a/c51f6d8957113a1d8a2f0c7ad588beb0.jpg'
    ],
    3: [
        '/static/images/storefront/83.webp', '/static/images/storefront/84.webp', '/static/images/storefront/85.webp',
        '/static/images/storefront/86.webp', '/static/images/storefront/87.webp', '/static/images/storefront/162.webp',
        '/static/images/storefront/163.webp', '/static/images/storefront/164.webp', '/static/images/storefront/165.webp',
        '/static/images/storefront/166.webp', '/static/images/catalog/5728b0b1a24dfa1f.jpg', '/static/images/catalog/d6c0e17fac16b3c9.jpg'
    ],
    4: [
        '/static/images/storefront/177.webp', '/static/images/storefront/178.webp', '/static/images/storefront/179.webp',
        '/static/images/storefront/180.webp', '/static/images/storefront/181.webp', '/static/images/storefront/172.webp',
        '/static/images/storefront/173.webp', '/static/images/storefront/174.webp', '/static/images/storefront/175.webp',
        '/static/images/storefront/176.webp', '/static/images/catalog/52f555117a200f4b.jpg', '/static/images/catalog/09ddcd01f868485a.jpg'
    ],
    5: [
        '/static/images/storefront/88.webp', '/static/images/storefront/89.webp', '/static/images/storefront/90.webp',
        '/static/images/storefront/91.webp', '/static/images/storefront/92.webp', '/static/images/storefront/185.webp',
        '/static/images/storefront/186.webp', '/static/images/storefront/187.webp', '/static/images/storefront/188.webp',
        '/static/images/storefront/189.webp', '/static/images/catalog/c05ce10bc673f2bd.jpg', '/static/images/catalog/1fd3c541504d3504.jpg',
        '/static/images/catalog/bb7b4acbe4fe7832.jpg'
    ],
    6: [
        '/static/images/storefront/48.webp', '/static/images/storefront/49.webp', '/static/images/storefront/50.webp',
        '/static/images/storefront/51.webp', '/static/images/storefront/52.webp', '/static/images/storefront/53.webp',
        '/static/images/storefront/54.webp', '/static/images/storefront/55.webp', '/static/images/storefront/56.webp',
        '/static/images/storefront/57.webp', '/static/images/storefront/58.webp', '/static/images/storefront/59.webp',
        '/static/images/storefront/60.webp', '/static/images/storefront/11.webp', '/static/images/storefront/12.webp',
        '/static/images/storefront/13.webp', '/static/images/storefront/14.webp', '/static/images/storefront/15.webp',
        '/static/images/catalog/1d2b90e9593ea950.jpg'
    ],
    7: [
        '/static/images/storefront/1.webp', '/static/images/storefront/2.webp', '/static/images/storefront/3.webp',
        '/static/images/storefront/4.webp', '/static/images/storefront/5.webp', '/static/images/storefront/6.webp',
        '/static/images/storefront/7.webp', '/static/images/storefront/8.webp', '/static/images/storefront/9.webp',
        '/static/images/storefront/10.webp', '/static/images/storefront/118.webp', '/static/images/storefront/119.webp',
        '/static/images/storefront/120.webp', '/static/images/catalog/42b2f8a7cabd17ed.jpg', '/static/images/catalog/72e1c1864fbf6d4a.jpg'
    ],
    8: [
        '/static/images/storefront/93.webp', '/static/images/storefront/94.webp', '/static/images/storefront/95.webp',
        '/static/images/storefront/96.webp', '/static/images/storefront/97.webp', '/static/images/storefront/98.webp',
        '/static/images/storefront/190.webp', '/static/images/storefront/191.webp', '/static/images/storefront/192.webp',
        '/static/images/storefront/193.webp', '/static/images/storefront/194.webp', '/static/images/storefront/182.webp',
        '/static/images/storefront/183.webp', '/static/images/storefront/184.webp', '/static/images/storefront/154.webp',
        '/static/images/storefront/155.webp', '/static/images/storefront/156.webp', '/static/images/storefront/157.webp',
        '/static/images/storefront/158.webp', '/static/images/catalog/4e7510a29a03b087.jpg'
    ],
    9: [
        '/static/images/storefront/121.webp', '/static/images/storefront/122.webp', '/static/images/storefront/123.webp',
        '/static/images/storefront/124.webp', '/static/images/storefront/125.webp', '/static/images/storefront/126.webp',
        '/static/images/storefront/127.webp', '/static/images/storefront/128.webp', '/static/images/storefront/129.webp',
        '/static/images/storefront/130.webp', '/static/images/storefront/131.webp', '/static/images/storefront/132.webp',
        '/static/images/storefront/133.webp', '/static/images/storefront/134.webp', '/static/images/storefront/135.webp',
        '/static/images/storefront/136.webp', '/static/images/storefront/159.webp', '/static/images/storefront/160.webp',
        '/static/images/storefront/161.webp',
        'https://salt.tikicdn.com/cache/280x280/ts/product/cb/a9/4c/48456b4f0f67bcb75829ed6243b4441f.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/b2/a8/95/c5229c9913879eec850801623a8559fe.jpg',
        'https://salt.tikicdn.com/cache/280x280/ts/product/e2/55/5e/c24cacac7ec162e3b1232a33192b9aad.jpg'
    ],
    10: [
        'https://salt.tikicdn.com/cache/280x280/ts/product/1f/a2/3b/e9883cef14604ee43cdf7b19324869ce.jpg',
        'https://salt.tikicdn.com/cache/280x280/media/catalog/product/product/4a/70/5c/d10a243a43febb9c23212ad001ae2bf3.png',
        'https://salt.tikicdn.com/cache/280x280/ts/product/56/c2/a1/e4e91634577ed5633d103620901caf3c.png',
        'https://salt.tikicdn.com/cache/280x280/ts/product/14/0c/f5/8532eab602059e2751dbe835c7366f42.png',
        'https://salt.tikicdn.com/cache/280x280/ts/product/6e/b1/d8/66f2442106cd08c042fa4bf7f078184e.png'
    ],
    11: [
        '/static/images/storefront/137.webp', '/static/images/storefront/138.webp', '/static/images/storefront/139.webp',
        '/static/images/storefront/140.webp', '/static/images/storefront/141.webp', '/static/images/storefront/142.webp',
        '/static/images/storefront/143.webp', '/static/images/storefront/144.webp', '/static/images/storefront/145.webp',
        '/static/images/storefront/146.webp', '/static/images/storefront/147.webp', '/static/images/storefront/148.webp',
        '/static/images/storefront/149.webp', '/static/images/storefront/150.webp', '/static/images/storefront/151.webp',
        '/static/images/storefront/152.webp', '/static/images/storefront/153.webp', '/static/images/catalog/c05ce10bc673f2bd.jpg'
    ]
}


def public_product(row):
    result = dict(row)
    if result.get("raw_item_id") is not None:
        result['raw_item_id'] = str(result['raw_item_id'])
    if result.get('catalog_source') in ('amazon-2023', 'tiki-vn'):
        result['commerce_simulated'] = False
        result['image_kind'] = 'vietnamese_product'
        clean_name = re.sub(r'\s*\([^)]*\)', '', result.get('name') or '').strip()
        clean_name = re.sub(r'\s+', ' ', clean_name)
        if clean_name:
            result['name'] = clean_name
            result['description'] = f'{clean_name}. Kiểm tra màu sắc, phiên bản, giá và số lượng trước khi đặt hàng.'

        cat_id = result.get('category_id') or 1
        prod_id = result.get('id') or 1
        pool = VERIFIED_CATEGORY_IMAGES.get(cat_id) or VERIFIED_CATEGORY_IMAGES[1]

        curr_img = result.get('image_url') or ''
        if not curr_img or curr_img not in pool:
            img = pool[prod_id % len(pool)]
            result['image_url'] = img
            result['images'] = [img]
        else:
            result['image_url'] = curr_img
            result['images'] = [curr_img]

        op, price = result.get('original_price') or 0, result.get('price') or 0
        result['discount_percent'] = round((op - price) * 100 / op) if op > price > 0 else 0
        return result
    if result.get('catalog_source') == 'taobao-mm':
        result['commerce_simulated'] = True
        result['category_name'] = f"Nhóm {result['category_id']-10000:03d}"
        result['image_kind'] = 'anonymous_identity'
        from app.storefront import presentation
        display = presentation(result['id'])
        if display:
            result['original_category_name'] = result['category_name']
            result.update(display)
            result['image_kind'] = 'paired_illustrative_product'
            op, price = result.get('original_price') or 0, result.get('price') or 0
            result['discount_percent'] = round((op - price) * 100 / op) if op > price > 0 else 0
    return result
