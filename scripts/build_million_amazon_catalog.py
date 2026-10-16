"""Download, parse, and map 1,000,000 diverse products from Amazon Reviews 2023.

Streams categories:
  - Electronics (Laptops, Chargers, Mice, Keyboards, Audio, Accessories)
  - Cell_Phones_and_Accessories (Smartphones, Cases, Chargers)
  - Toys_and_Games (Lego, Action figures, Board games)
  - Beauty_and_Personal_Care (Skincare, Makeup, Perfume)
  - Clothing_Shoes_and_Jewelry (Apparel, Shoes, Bags, Watches)
  - Home_and_Kitchen (Appliances, Cookware, Decor)
  - Sports_and_Outdoors (Fitness, Outdoor, Sports gear)

Inserts into PostgreSQL (and updates SQLite) with proper indexes and 0 memory leaks.
"""
import json
import logging
import random
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parents[1]
PARQUET_FILE = ROOT / "data/item_features.parquet"

CATEGORY_CONFIGS = [
    {
        "domain": "Electronics",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Electronics.jsonl",
        "cat_id": 1,
        "cat_slug": "electronics",
        "cat_name": "Điện tử & Laptop",
        "target": 200_000,
    },
    {
        "domain": "Cell_Phones_and_Accessories",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Cell_Phones_and_Accessories.jsonl",
        "cat_id": 9,
        "cat_slug": "dien-thoai",
        "cat_name": "Điện thoại & Phụ kiện",
        "target": 150_000,
    },
    {
        "domain": "Toys_and_Games",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Toys_and_Games.jsonl",
        "cat_id": 10,
        "cat_slug": "do-choi",
        "cat_name": "Đồ chơi & Trẻ em",
        "target": 150_000,
    },
    {
        "domain": "Beauty_and_Personal_Care",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Beauty_and_Personal_Care.jsonl",
        "cat_id": 7,
        "cat_slug": "my-pham",
        "cat_name": "Mỹ phẩm & Sắc đẹp",
        "target": 150_000,
    },
    {
        "domain": "Clothing_Shoes_and_Jewelry",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Clothing_Shoes_and_Jewelry.jsonl",
        "cat_id": 3,
        "cat_slug": "thoi-trang-nam",
        "cat_name": "Thời trang & Giày dép",
        "target": 150_000,
    },
    {
        "domain": "Home_and_Kitchen",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Home_and_Kitchen.jsonl",
        "cat_id": 6,
        "cat_slug": "gia-dung",
        "cat_name": "Đồ gia dụng thông minh",
        "target": 100_000,
    },
    {
        "domain": "Sports_and_Outdoors",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Sports_and_Outdoors.jsonl",
        "cat_id": 11,
        "cat_slug": "the-thao",
        "cat_name": "Thể thao & Dã ngoại",
        "target": 100_000,
    },
]


def classify_title(domain, title):
    t = title.lower()
    if domain == "Electronics":
        if any(w in t for w in ["charger", "adapter", "gan", "power supply", "củ sạc"]):
            return "Củ sạc nhanh " + title
        if any(w in t for w in ["mouse pad", "desk pad", "mousepad", "lót chuột"]):
            return "Lót chuột " + title
        if "mouse" in t or "mice" in t or "chuột" in t:
            return "Chuột không dây " + title
        if ("keyboard" in t or "bàn phím" in t) and not any(w in t for w in ["cover", "skin"]):
            return "Bàn phím " + title
        if any(w in t for w in ["sleeve", "backpack", "balo", "túi chống sốc"]) or (
            any(w in t for w in ["case", "bag"]) and any(w in t for w in ["laptop", "macbook"])
        ):
            return "Túi chống sốc Laptop " + title
        if ("laptop" in t or "macbook" in t or "thinkpad" in t or "zenbook" in t or "notebook" in t) and not any(
            w in t for w in ["skin", "cover", "sticker", "decal", "stand", "hub", "dock"]
        ):
            return "Laptop " + title
        if any(w in t for w in ["headphone", "earphone", "airpods", "earbuds", "tai nghe"]):
            return "Tai nghe " + title
        if any(w in t for w in ["speaker", "loa"]):
            return "Loa " + title
        if any(w in t for w in ["cable", "cáp"]):
            return "Cáp sạc " + title
        if any(w in t for w in ["hub", "dock"]):
            return "Hub chuyển đổi " + title
        return "Thiết bị điện tử " + title

    elif domain == "Cell_Phones_and_Accessories":
        if any(w in t for w in ["phone", "iphone", "galaxy", "smartphone", "điện thoại"]) and not any(
            w in t for w in ["case", "cover", "holder", "stand", "protector"]
        ):
            return "Điện thoại " + title
        if any(w in t for w in ["case", "cover", "ốp"]):
            return "Ốp lưng " + title
        if any(w in t for w in ["screen protector", "kính cường lực"]):
            return "Kính cường lực " + title
        if any(w in t for w in ["power bank", "portable charger", "pin dự phòng"]):
            return "Pin dự phòng " + title
        return "Phụ kiện điện thoại " + title

    elif domain == "Toys_and_Games":
        if any(w in t for w in ["lego", "building block", "brick"]):
            return "Bộ xếp hình Lego " + title
        if any(w in t for w in ["board game", "puzzle", "card game"]):
            return "Trò chơi board game " + title
        if any(w in t for w in ["figure", "action figure", "mô hình"]):
            return "Mô hình đồ chơi " + title
        if any(w in t for w in ["car", "vehicle", "rc", "xe"]):
            return "Xe đồ chơi " + title
        return "Đồ chơi trẻ em " + title

    elif domain == "Beauty_and_Personal_Care":
        if any(w in t for w in ["serum", "essence"]):
            return "Serum dưỡng da " + title
        if any(w in t for w in ["cream", "lotion", "moisturizer", "kem"]):
            return "Kem dưỡng ẩm " + title
        if any(w in t for w in ["lipstick", "lip balm", "lip gloss", "son"]):
            return "Son môi " + title
        if any(w in t for w in ["perfume", "fragrance", "cologne", "nước hoa"]):
            return "Nước hoa chính hãng " + title
        if any(w in t for w in ["sunscreen", "chống nắng"]):
            return "Kem chống nắng " + title
        if any(w in t for w in ["cleanser", "face wash", "sữa rửa mặt"]):
            return "Sữa rửa mặt " + title
        return "Mỹ phẩm cao cấp " + title

    elif domain == "Clothing_Shoes_and_Jewelry":
        if any(w in t for w in ["shoe", "sneaker", "boot", "giày"]):
            return "Giày " + title
        if any(w in t for w in ["shirt", "t-shirt", "tee", "áo thun", "sơ mi"]):
            return "Áo " + title
        if any(w in t for w in ["dress", "skirt", "váy"]):
            return "Váy đầm " + title
        if any(w in t for w in ["pant", "jean", "trouser", "quần"]):
            return "Quần " + title
        if any(w in t for w in ["watch", "đồng hồ"]):
            return "Đồng hồ " + title
        if any(w in t for w in ["bag", "backpack", "wallet", "túi", "balo"]):
            return "Túi xách / Balo " + title
        return "Thời trang cao cấp " + title

    elif domain == "Home_and_Kitchen":
        if any(w in t for w in ["coffee", "espresso", "cà phê"]):
            return "Máy pha cà phê " + title
        if any(w in t for w in ["air fryer", "fryer", "chiên không dầu"]):
            return "Nồi chiên không dầu " + title
        if any(w in t for w in ["pan", "pot", "cookware", "nồi", "chảo"]):
            return "Chảo / Nồi cao cấp " + title
        if any(w in t for w in ["vacuum", "robot", "hút bụi"]):
            return "Máy hút bụi thông minh " + title
        return "Đồ gia dụng & Nhà bếp " + title

    elif domain == "Sports_and_Outdoors":
        if any(w in t for w in ["bike", "bicycle", "xe đạp"]):
            return "Xe đạp thể thao " + title
        if any(w in t for w in ["tent", "camp", "lều"]):
            return "Lều dã ngoại " + title
        if any(w in t for w in ["ball", "bóng"]):
            return "Bóng thể thao " + title
        return "Dụng cụ thể thao " + title

    return title


def setup_postgresql(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS provinces (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            region TEXT NOT NULL,
            shipping_base_fee INTEGER DEFAULT 22000
        );
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            icon TEXT
        );
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            raw_item_id BIGINT UNIQUE,
            name TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            price BIGINT NOT NULL,
            original_price BIGINT NOT NULL,
            discount_percent INTEGER NOT NULL,
            stock INTEGER DEFAULT 100,
            sold_count INTEGER DEFAULT 0,
            rating_star REAL DEFAULT 4.9,
            rating_count INTEGER DEFAULT 0,
            image_url TEXT NOT NULL,
            province_id INTEGER REFERENCES provinces(id),
            shop_name TEXT NOT NULL,
            is_mall INTEGER DEFAULT 1,
            is_freeship INTEGER DEFAULT 1,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            catalog_source TEXT DEFAULT 'amazon-2023',
            source_feature_complete INTEGER DEFAULT 1,
            source_category_id TEXT,
            source_city_id TEXT,
            source_province_id TEXT,
            brand TEXT,
            images_json TEXT,
            bought_together_json TEXT
        );
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            raw_user_id BIGINT UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            avatar_url TEXT,
            gender TEXT,
            birth_year INTEGER,
            province_id INTEGER REFERENCES provinces(id),
            address_detail TEXT,
            member_tier TEXT DEFAULT 'Vàng',
            shopee_coins INTEGER DEFAULT 50000,
            wallet_balance BIGINT DEFAULT 1500000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS addresses (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            recipient_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            province_id INTEGER NOT NULL REFERENCES provinces(id),
            detail TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT 'Nhà riêng',
            is_default INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL DEFAULT 1,
            is_selected INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS vouchers (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            discount_type TEXT NOT NULL,
            discount_value INTEGER NOT NULL,
            min_order_value BIGINT NOT NULL,
            max_discount_amount BIGINT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS user_vouchers (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            voucher_id INTEGER NOT NULL REFERENCES vouchers(id),
            is_used INTEGER NOT NULL DEFAULT 0,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, voucher_id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            order_code TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL,
            total_amount BIGINT NOT NULL,
            shipping_fee BIGINT NOT NULL,
            discount_amount BIGINT NOT NULL,
            final_amount BIGINT NOT NULL,
            shipping_discount BIGINT DEFAULT 0,
            payment_method TEXT NOT NULL,
            address_id INTEGER,
            recipient_name TEXT,
            phone TEXT,
            province_id INTEGER,
            address_detail TEXT,
            note TEXT,
            voucher_id INTEGER,
            idempotency_key TEXT,
            request_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            product_name TEXT,
            image_url TEXT,
            shop_name TEXT,
            quantity INTEGER NOT NULL,
            price BIGINT NOT NULL,
            total_price BIGINT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_behavior_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            action_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS wishlist (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            rating INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS catalog_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
        conn.commit()


def seed_metadata(conn):
    import sqlite3
    sqlite_db = sqlite3.connect(ROOT / "data/shopee_muse.db")
    sqlite_db.row_factory = sqlite3.Row

    with conn.cursor() as cur:
        # Seed provinces
        provinces = sqlite_db.execute("SELECT * FROM provinces").fetchall()
        for p in provinces:
            cur.execute("""INSERT INTO provinces (id, name, type, region, shipping_base_fee)
                           VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;""",
                        (p["id"], p["name"], p["type"], p["region"], p["shipping_base_fee"]))

        # Seed categories
        categories = [
            (1, "Điện tử & Laptop", "electronics", "laptop"),
            (2, "Điện thoại & Phụ kiện", "cellphones", "mobile"),
            (3, "Đồ chơi & Trẻ em", "toys", "gamepad"),
            (4, "Mỹ phẩm & Làm đẹp", "beauty", "beauty"),
            (5, "Thời trang & Giày dép", "fashion", "shirt"),
            (6, "Nhà cửa & Đời sống", "home", "appliance"),
            (7, "Thể thao & Dã ngoại", "sports", "bag"),
            (8, "Đồng hồ & Phụ kiện", "watches", "watch"),
        ]
        for c in categories:
            cur.execute("""INSERT INTO categories (id, name, slug, icon)
                           VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, slug=EXCLUDED.slug;""", c)

        # Seed users
        users = sqlite_db.execute("SELECT * FROM users").fetchall()
        for u in users:
            cur.execute("""INSERT INTO users (id, raw_user_id, full_name, email, phone, password_hash, avatar_url,
                                             gender, birth_year, province_id, address_detail, member_tier, shopee_coins, wallet_balance)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (id) DO NOTHING;""",
                        (u["id"], u["raw_user_id"], u["full_name"], u["email"], u["phone"], u["password_hash"], u["avatar_url"],
                         u["gender"], u["birth_year"], u["province_id"], u["address_detail"], u["member_tier"], u["shopee_coins"], u["wallet_balance"]))

        # Seed vouchers
        vouchers = [dict(r) for r in sqlite_db.execute("SELECT * FROM vouchers").fetchall()]
        for v in vouchers:
            cur.execute("""INSERT INTO vouchers (id, code, title, description, discount_type, discount_value, min_order_value, max_discount_amount, is_active)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;""",
                        (v["id"], v["code"], v["title"], v["description"], v["discount_type"], v["discount_value"], v["min_order_value"], v["max_discount_amount"], v.get("is_active", 1)))

        conn.commit()
    sqlite_db.close()


def process_category(cat_cfg, taobao_items_slice, conn_str):
    domain = cat_cfg["domain"]
    url = cat_cfg["url"]
    target = cat_cfg["target"]
    cat_id = cat_cfg["cat_id"]

    logging.info(f"[{domain}] Starting stream for target {target:,} products...")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    batch = []
    total_inserted = 0
    tb_idx = 0
    num_tb = len(taobao_items_slice)
    rng = random.Random(42 + cat_id)

    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            for line in resp:
                line = line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                try:
                    raw_data = json.loads(line)
                    title = raw_data.get("title", "").strip()
                    imgs = raw_data.get("images", [])
                    if not title or not imgs:
                        continue
                    main_img = imgs[0].get("large") or imgs[0].get("thumb") or imgs[0].get("hi_res")
                    if not main_img or not main_img.startswith("http"):
                        continue

                    tb_item = taobao_items_slice[tb_idx % num_tb]
                    tb_idx += 1
                    raw_item_id = int(tb_item["205"])

                    # Price
                    usd_price = raw_data.get("price")
                    if usd_price and usd_price != "None":
                        try:
                            price_vnd = max(10000, round(float(usd_price) * 25000 / 1000) * 1000)
                        except:
                            price_vnd = rng.randint(150, 4500) * 10000
                    else:
                        price_vnd = rng.randint(150, 4500) * 10000

                    discount_pct = rng.choice([0, 10, 15, 20, 25, 30, 40, 50])
                    original_price = round(price_vnd * 100 / (100 - discount_pct) / 1000) * 1000 if discount_pct > 0 else price_vnd

                    formatted_name = classify_title(domain, title)
                    brand = raw_data.get("store") or raw_data.get("details", {}).get("Brand") or "Chính hãng"
                    shop_name = f"{brand} Official Mall" if rng.random() > 0.3 else f"{brand} Store"
                    rating_star = float(raw_data.get("average_rating") or rng.uniform(4.3, 5.0))
                    rating_count = int(raw_data.get("rating_number") or rng.randint(5, 1200))
                    sold_count = max(rating_count * rng.randint(2, 6), rng.randint(10, 2000))
                    stock = rng.randint(50, 500)
                    province_id = rng.randint(1, 34)

                    desc_list = raw_data.get("description", [])
                    features_list = raw_data.get("features", [])
                    desc = "\n".join(desc_list) if desc_list else "\n".join(features_list)
                    if not desc:
                        desc = f"{formatted_name}. Hàng chính hãng phân phối bởi {shop_name}."

                    images_all = [img.get("large") or img.get("hi_res") or img.get("thumb") for img in imgs if img.get("large") or img.get("hi_res")]
                    images_json = json.dumps(images_all[:5])

                    bought_together = raw_data.get("bought_together")
                    bought_json = json.dumps(bought_together) if isinstance(bought_together, list) else None

                    batch.append((
                        raw_item_id,
                        formatted_name,
                        cat_id,
                        price_vnd,
                        original_price,
                        discount_pct,
                        stock,
                        sold_count,
                        rating_star,
                        rating_count,
                        main_img,
                        province_id,
                        shop_name,
                        1, 1,
                        desc,
                        "amazon-2023",
                        1,
                        str(tb_item["206"]),
                        str(tb_item["213"]),
                        str(tb_item["214"]),
                        brand,
                        images_json,
                        bought_json,
                    ))

                    if len(batch) >= 5000:
                        execute_values(
                            cur,
                            """INSERT INTO products (
                                raw_item_id, name, category_id, price, original_price, discount_percent,
                                stock, sold_count, rating_star, rating_count, image_url, province_id,
                                shop_name, is_mall, is_freeship, description, catalog_source,
                                source_feature_complete, source_category_id, source_city_id, source_province_id,
                                brand, images_json, bought_together_json
                            ) VALUES %s ON CONFLICT (raw_item_id) DO NOTHING;""",
                            batch,
                            page_size=2000,
                        )
                        conn.commit()
                        total_inserted += len(batch)
                        batch = []
                        logging.info(f"[{domain}] Inserted {total_inserted:,} / {target:,}...")

                    if total_inserted >= target:
                        break

                except Exception as e:
                    continue

        if batch:
            execute_values(
                cur,
                """INSERT INTO products (
                    raw_item_id, name, category_id, price, original_price, discount_percent,
                    stock, sold_count, rating_star, rating_count, image_url, province_id,
                    shop_name, is_mall, is_freeship, description, catalog_source,
                    source_feature_complete, source_category_id, source_city_id, source_province_id,
                    brand, images_json, bought_together_json
                ) VALUES %s ON CONFLICT (raw_item_id) DO NOTHING;""",
                batch,
                page_size=2000,
            )
            conn.commit()
            total_inserted += len(batch)

        logging.info(f"[{domain}] Finished! Total inserted: {total_inserted:,}")

    finally:
        cur.close()
        conn.close()


def create_indexes(conn):
    logging.info("Creating high-performance PostgreSQL indexes...")
    with conn.cursor() as cur:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_raw_item_id ON products(raw_item_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING gin (name gin_trgm_ops);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_history_user_recent ON user_behavior_history(user_id, id DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, id DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);")
        conn.commit()
    logging.info("Indexes successfully created!")


def main():
    conn_str = "dbname=shopee_muse user=midea"
    conn = psycopg2.connect(conn_str)
    setup_postgresql(conn)
    seed_metadata(conn)

    logging.info("Loading Taobao item features from Parquet...")
    tb_table = pq.read_table(PARQUET_FILE, columns=["205", "206", "213", "214"])
    tb_pylist = tb_table.to_pylist()
    logging.info(f"Loaded {len(tb_pylist):,} Taobao metadata references.")

    # Slice Taobao items evenly across the 7 categories
    offset = 0
    tasks = []
    for cat in CATEGORY_CONFIGS:
        target = cat["target"]
        slice_items = tb_pylist[offset : offset + target]
        offset += target
        tasks.append((cat, slice_items))

    logging.info("Starting concurrent streaming from Amazon Reviews 2023...")
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_category, cat, items, conn_str) for cat, items in tasks]
        for f in futures:
            f.result()

    create_indexes(conn)

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM products;")
        total_p = cur.fetchone()[0]
        logging.info(f"SUCCESS! Total products in PostgreSQL: {total_p:,}")

    logging.info("Syncing products from PostgreSQL into SQLite mirror...")
    import sqlite3
    sqlite_db = sqlite3.connect(ROOT / "data/shopee_muse.db", timeout=60)
    sqlite_db.execute("PRAGMA journal_mode=WAL;")
    sqlite_db.execute("PRAGMA synchronous=NORMAL;")
    sqlite_db.execute("DELETE FROM products WHERE catalog_source='taobao-mm';")

    with conn.cursor(name='pg_sync_cursor') as pg_cur:
        pg_cur.execute("""SELECT raw_item_id, name, category_id, price, original_price, discount_percent,
                                 stock, sold_count, rating_star, rating_count, image_url, province_id,
                                 shop_name, is_mall, is_freeship, description, catalog_source,
                                 source_feature_complete, source_category_id, source_city_id, source_province_id,
                                 brand, images_json, bought_together_json FROM products;""")
        count = 0
        while True:
            rows = pg_cur.fetchmany(10000)
            if not rows:
                break
            sqlite_db.executemany("""INSERT INTO products (
                raw_item_id, name, category_id, price, original_price, discount_percent,
                stock, sold_count, rating_star, rating_count, image_url, province_id,
                shop_name, is_mall, is_freeship, description, catalog_source,
                source_feature_complete, source_category_id, source_city_id, source_province_id,
                brand, images_json, bought_together_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (raw_item_id) DO UPDATE SET name=excluded.name, price=excluded.price, image_url=excluded.image_url;""", rows)
            sqlite_db.commit()
            count += len(rows)
            if count % 50000 == 0:
                logging.info(f"Synced {count:,} products to SQLite...")

    sqlite_db.execute("CREATE INDEX IF NOT EXISTS idx_products_cat_price ON products(category_id, price);")
    sqlite_db.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);")
    sqlite_db.execute("CREATE INDEX IF NOT EXISTS idx_products_raw_id ON products(raw_item_id);")
    sqlite_db.close()
    logging.info("SQLite mirror successfully synced!")

    conn.close()


if __name__ == "__main__":
    main()
