#!/usr/bin/env python3
"""One-click setup script to upload Shopee MUSE catalog (15,000 products) to Neon Serverless PostgreSQL."""
import os
import sys
import time
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PG_SCHEMA = """
DROP TABLE IF EXISTS user_behavior_history CASCADE;
DROP TABLE IF EXISTS cart_items CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS wishlist CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS user_vouchers CASCADE;
DROP TABLE IF EXISTS addresses CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS provinces CASCADE;
DROP TABLE IF EXISTS vouchers CASCADE;
DROP TABLE IF EXISTS users CASCADE;

CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    icon VARCHAR(50)
);

CREATE TABLE provinces (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50),
    region VARCHAR(50),
    shipping_base_fee INTEGER DEFAULT 20000
);

CREATE TABLE vouchers (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    discount_type VARCHAR(20) NOT NULL,
    discount_value INTEGER NOT NULL,
    min_order_value INTEGER DEFAULT 0,
    max_discount_amount INTEGER
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    raw_user_id VARCHAR(100),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    gender VARCHAR(10),
    birth_year INTEGER,
    province_id INTEGER REFERENCES provinces(id),
    address_detail TEXT,
    member_tier VARCHAR(50) DEFAULT 'Thành viên Mới',
    shopee_coins INTEGER DEFAULT 0,
    wallet_balance BIGINT DEFAULT 0
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    raw_item_id VARCHAR(100),
    name TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    price INTEGER NOT NULL,
    original_price INTEGER NOT NULL,
    discount_percent INTEGER DEFAULT 0,
    stock INTEGER DEFAULT 100,
    sold_count INTEGER DEFAULT 0,
    rating_star NUMERIC(2,1) DEFAULT 5.0,
    rating_count INTEGER DEFAULT 0,
    image_url TEXT,
    province_id INTEGER REFERENCES provinces(id),
    shop_name VARCHAR(255),
    is_mall BOOLEAN DEFAULT FALSE,
    is_freeship BOOLEAN DEFAULT TRUE,
    description TEXT,
    catalog_source VARCHAR(50) DEFAULT 'tiki-vn',
    source_feature_complete INTEGER DEFAULT 1,
    source_category_id VARCHAR(100),
    source_city_id VARCHAR(100),
    source_province_id VARCHAR(100),
    brand VARCHAR(100),
    images_json TEXT,
    bought_together_json TEXT
);

CREATE INDEX idx_pg_products_cat_sold ON products(category_id, sold_count DESC);
CREATE INDEX idx_pg_products_sold ON products(sold_count DESC);
CREATE INDEX idx_pg_products_cat_rating ON products(category_id, rating_star DESC);

CREATE TABLE user_behavior_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    raw_user_id VARCHAR(100),
    product_id INTEGER REFERENCES products(id),
    raw_item_id VARCHAR(100),
    action_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_pg_user_hist ON user_behavior_history(user_id, id DESC);
"""

def setup_neon(db_url: str):
    print(f"🚀 Connecting to Neon PostgreSQL...")
    t0 = time.time()
    try:
        pg_conn = psycopg2.connect(db_url)
        pg_conn.autocommit = True
        cur = pg_conn.cursor()
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return

    print("📋 Creating database tables on Neon...")
    cur.execute(PG_SCHEMA)
    print("✅ Schema created successfully!")

    # Connect to local compact SQLite catalog
    sqlite_path = ROOT / "data/cloud_catalog.db"
    if not sqlite_path.exists():
        sqlite_path = ROOT / "data/shopee_muse.db"
    sq_conn = sqlite3.connect(str(sqlite_path))
    sq_cur = sq_conn.cursor()

    # 1. Categories
    print("📦 Uploading categories...")
    cats = sq_cur.execute("SELECT id, name, slug, icon FROM categories WHERE id <= 11").fetchall()
    execute_values(cur, "INSERT INTO categories (id, name, slug, icon) VALUES %s", cats)

    # 2. Provinces
    print("📦 Uploading provinces...")
    provs = sq_cur.execute("SELECT id, name, type, region, shipping_base_fee FROM provinces").fetchall()
    execute_values(cur, "INSERT INTO provinces (id, name, type, region, shipping_base_fee) VALUES %s", provs)

    # 3. Vouchers
    print("📦 Uploading vouchers...")
    vouchers = sq_cur.execute("SELECT code, title, description, discount_type, discount_value, min_order_value, max_discount_amount FROM vouchers").fetchall()
    execute_values(cur, "INSERT INTO vouchers (code, title, description, discount_type, discount_value, min_order_value, max_discount_amount) VALUES %s", vouchers)

    # 4. Users
    print("📦 Uploading demo users...")
    users = sq_cur.execute("SELECT raw_user_id, full_name, email, phone, password_hash, avatar_url, gender, birth_year, province_id, address_detail, member_tier, shopee_coins, wallet_balance FROM users").fetchall()
    execute_values(cur, """
        INSERT INTO users (raw_user_id, full_name, email, phone, password_hash, avatar_url, gender, birth_year, province_id, address_detail, member_tier, shopee_coins, wallet_balance)
        VALUES %s
    """, users)

    # 5. Products (15,000 products)
    print("📦 Uploading 15,000 products to Neon...")
    prod_fields = """
        raw_item_id, name, category_id, price, original_price, discount_percent,
        stock, sold_count, rating_star, rating_count, image_url, province_id,
        shop_name, is_mall, is_freeship, description, catalog_source,
        source_feature_complete, source_category_id, source_city_id, source_province_id,
        brand, images_json, bought_together_json
    """
    prods = sq_cur.execute(f"SELECT {prod_fields} FROM products WHERE id <= 15000").fetchall()
    execute_values(cur, f"INSERT INTO products ({prod_fields}) VALUES %s", prods, page_size=2000)

    # 6. User Behavior History
    print("📦 Uploading user behavior histories...")
    hist = sq_cur.execute("SELECT user_id, raw_user_id, product_id, raw_item_id, action_type FROM user_behavior_history WHERE product_id <= 15000 OR product_id IS NULL").fetchall()
    if hist:
        execute_values(cur, "INSERT INTO user_behavior_history (user_id, raw_user_id, product_id, raw_item_id, action_type) VALUES %s", hist, page_size=2000)

    cur.execute("SELECT count(*) FROM products")
    total_prods = cur.fetchone()[0]
    
    cur.close()
    pg_conn.close()
    sq_conn.close()
    print(f"🎉 Complete! Neon PostgreSQL is ready with {total_prods:,} products in {time.time() - t0:.2f}s!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = os.getenv("DATABASE_URL")
    if not url:
        print("Usage: python scripts/setup_neon_db.py 'postgresql://user:pass@ep-...neon.tech/neondb?sslmode=require'")
        sys.exit(1)
    setup_neon(url)
