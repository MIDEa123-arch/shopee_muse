import sqlite3
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


def public_product(row):
    result = dict(row)
    if result.get("raw_item_id") is not None:
        result['raw_item_id'] = str(result['raw_item_id'])
    return result
