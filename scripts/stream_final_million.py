"""Stream and insert remaining ~520,000 Amazon Reviews 2023 products to reach 1,000,000+.

Streams:
  - Cell_Phones_and_Accessories (target: 150,000) -> Cat 9 (Điện Thoại & Máy Tính Bảng)
  - Toys_and_Games (target: 150,000) -> Cat 10 (Đồ Chơi & Trẻ Em)
  - Sports_and_Outdoors (target: 100,000) -> Cat 11 (Thể Thao & Dã Ngoại)
  - Musical_Instruments (target: 60,000) -> Cat 2 (Âm Thanh & Tai Nghe)
  - Baby_Products (target: 60,000) -> Cat 10 (Đồ Chơi & Mẹ Bé)

Total will reach over 1,000,000 real products.
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
        "domain": "Cell_Phones_and_Accessories",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Cell_Phones_and_Accessories.jsonl",
        "cat_id": 9,
        "cat_slug": "dien-thoai",
        "cat_name": "Điện Thoại & Máy Tính Bảng",
        "target": 150_000,
    },
    {
        "domain": "Toys_and_Games",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Toys_and_Games.jsonl",
        "cat_id": 10,
        "cat_slug": "do-choi",
        "cat_name": "Đồ Chơi & Trẻ Em",
        "target": 150_000,
    },
    {
        "domain": "Sports_and_Outdoors",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Sports_and_Outdoors.jsonl",
        "cat_id": 11,
        "cat_slug": "the-thao",
        "cat_name": "Thể Thao & Dã Ngoại",
        "target": 100_000,
    },
    {
        "domain": "Musical_Instruments",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Musical_Instruments.jsonl",
        "cat_id": 2,
        "cat_slug": "am-thanh",
        "cat_name": "Âm Thanh & Thiết Bị Nhạc Cụ",
        "target": 60_000,
    },
    {
        "domain": "Baby_Products",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Baby_Products.jsonl",
        "cat_id": 10,
        "cat_slug": "do-choi",
        "cat_name": "Đồ Chơi & Đồ Dùng Mẹ Bé",
        "target": 60_000,
    },
]


def classify_title(domain, title):
    t = title.lower()
    if domain == "Cell_Phones_and_Accessories":
        if any(w in t for w in ["phone", "iphone", "galaxy", "smartphone", "điện thoại"]) and not any(
            w in t for w in ["case", "cover", "holder", "stand", "protector"]
        ):
            return "Điện thoại thông minh " + title
        if any(w in t for w in ["case", "cover", "ốp"]):
            return "Ốp lưng " + title
        if any(w in t for w in ["screen protector", "tempered glass", "kính cường lực"]):
            return "Kính cường lực " + title
        if any(w in t for w in ["power bank", "portable charger", "pin dự phòng"]):
            return "Pin sạc dự phòng " + title
        if any(w in t for w in ["car mount", "holder", "stand"]):
            return "Giá đỡ điện thoại " + title
        return "Phụ kiện điện thoại " + title

    elif domain == "Toys_and_Games":
        if any(w in t for w in ["lego", "building block", "brick"]):
            return "Bộ xếp hình Lego " + title
        if any(w in t for w in ["board game", "puzzle", "card game"]):
            return "Trò chơi board game " + title
        if any(w in t for w in ["figure", "action figure", "mô hình"]):
            return "Mô hình đồ chơi Anime/Action " + title
        if any(w in t for w in ["car", "vehicle", "rc", "drone", "xe"]):
            return "Xe điều khiển đồ chơi " + title
        if any(w in t for w in ["plush", "stuffed", "gấu bông"]):
            return "Thú nhồi bông cao cấp " + title
        return "Đồ chơi trẻ em thông minh " + title

    elif domain == "Sports_and_Outdoors":
        if any(w in t for w in ["gym", "fitness", "dumbbell", "resistance", "tập gym"]):
            return "Dụng cụ tập Gym & Yoga " + title
        if any(w in t for w in ["camp", "tent", "sleeping bag", "lều"]):
            return "Lều cắm trại dã ngoại " + title
        if any(w in t for w in ["bottle", "flask", "bình nước"]):
            return "Bình nước thể thao " + title
        if any(w in t for w in ["bike", "bicycle", "xe đạp"]):
            return "Phụ kiện xe đạp thể thao " + title
        if any(w in t for w in ["backpack", "hiking", "balo"]):
            return "Balo dã ngoại chống nước " + title
        return "Dụng cụ thể thao dã ngoại " + title

    elif domain == "Musical_Instruments":
        if any(w in t for w in ["guitar", "ukulele"]):
            return "Đàn Guitar & Phụ kiện " + title
        if any(w in t for w in ["microphone", "mic"]):
            return "Microphone thu âm chuyên nghiệp " + title
        if any(w in t for w in ["piano", "keyboard"]):
            return "Đàn Piano điện & Organ " + title
        if any(w in t for w in ["headphone", "earphone", "iem"]):
            return "Tai nghe kiểm âm chất lượng cao " + title
        if any(w in t for w in ["speaker", "amp", "amplifier"]):
            return "Loa & Amply cao cấp " + title
        return "Thiết bị âm thanh & Nhạc cụ " + title

    elif domain == "Baby_Products":
        if any(w in t for w in ["stroller", "pram", "xe đẩy"]):
            return "Xe đẩy em bé cao cấp " + title
        if any(w in t for w in ["toy", "rattle", "đồ chơi"]):
            return "Đồ chơi giáo dục trẻ em " + title
        if any(w in t for w in ["bottle", "feeder", "bình sữa"]):
            return "Bình sữa an toàn cho bé " + title
        return "Đồ dùng mẹ và bé chính hãng " + title

    return title


def process_category(cat_cfg, taobao_items_slice, conn_str):
    domain = cat_cfg["domain"]
    url = cat_cfg["url"]
    target = cat_cfg["target"]
    cat_id = cat_cfg["cat_id"]

    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM products WHERE category_id = %s AND catalog_source = 'amazon-2023'", (cat_id,))
    existing_in_cat = cur.fetchone()[0]
    if existing_in_cat >= target and domain != "Baby_Products":
        logging.info(f"[{domain}] Category {cat_id} already has {existing_in_cat:,} items. Skipping.")
        cur.close()
        conn.close()
        return

    needed = target
    logging.info(f"[{domain}] Starting stream for target {needed:,} products...")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    batch = []
    total_inserted = 0
    tb_idx = 0
    num_tb = len(taobao_items_slice)
    rng = random.Random(42 + cat_id + hash(domain) % 1000)

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

                    # Price in VND
                    usd_price = raw_data.get("price")
                    if usd_price and usd_price != "None":
                        try:
                            price_vnd = max(15000, round(float(usd_price) * 25000 / 1000) * 1000)
                        except Exception:
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
                    province_id = rng.choice([1, 2, 3, 4, 5, 6, 7, 8])

                    desc = raw_data.get("description", [])
                    if isinstance(desc, list):
                        desc = "\n".join(desc) if desc else formatted_name
                    desc = desc[:1000] if desc else formatted_name

                    valid_images = [img.get("large") or img.get("hi_res") or img.get("thumb") for img in imgs]
                    valid_images = [img for img in valid_images if img and img.startswith("http")][:6]
                    images_json = json.dumps(valid_images)

                    bought_json = json.dumps(raw_data.get("bought_together") or [])

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
                        total_inserted += cur.rowcount
                        batch = []
                        logging.info(f"[{domain}] Inserted {total_inserted:,} / {needed:,}...")

                    if total_inserted >= needed:
                        break

                except Exception as e:
                    conn.rollback()
                    logging.warning(f"[{domain}] Row processing error: {e}")
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
            total_inserted += cur.rowcount

        logging.info(f"[{domain}] Finished! Total inserted this run: {total_inserted:,}")

    except Exception as e:
        conn.rollback()
        logging.exception(f"[{domain}] Stream failure: {e}")
    finally:
        cur.close()
        conn.close()


def create_indexes(conn):
    logging.info("Ensuring PostgreSQL indexes are up to date...")
    with conn.cursor() as cur:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_raw_item_id ON products(raw_item_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING gin (name gin_trgm_ops);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_history_user_recent ON user_behavior_history(user_id, id DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, id DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);")
        conn.commit()
    logging.info("Indexes successfully created / verified!")


def sync_to_sqlite(conn):
    logging.info("Syncing products from PostgreSQL into SQLite mirror (data/shopee_muse.db)...")
    import sqlite3
    sqlite_db = sqlite3.connect(ROOT / "data/shopee_muse.db", timeout=120)
    sqlite_db.execute("PRAGMA journal_mode=WAL;")
    sqlite_db.execute("PRAGMA synchronous=NORMAL;")
    sqlite_db.execute("DELETE FROM products WHERE catalog_source='taobao-mm';")

    with conn.cursor(name="pg_sync_cursor_final") as pg_cur:
        pg_cur.itersize = 10000
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
            if count % 100000 == 0:
                logging.info(f"Synced {count:,} products to SQLite...")

    sqlite_db.execute("CREATE INDEX IF NOT EXISTS idx_products_cat_price ON products(category_id, price);")
    sqlite_db.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);")
    sqlite_db.execute("CREATE INDEX IF NOT EXISTS idx_products_raw_id ON products(raw_item_id);")
    sqlite_db.close()
    logging.info(f"SQLite mirror successfully synced! Total rows: {count:,}")


def main():
    conn_str = "dbname=shopee_muse user=midea"
    conn = psycopg2.connect(conn_str)

    logging.info("Loading Taobao item features from Parquet...")
    tb_table = pq.read_table(PARQUET_FILE, columns=["205", "206", "213", "214"])
    tb_pylist = tb_table.to_pylist()
    logging.info(f"Loaded {len(tb_pylist):,} Taobao metadata references.")

    # Offset to 1,000,000 to use 100% fresh, unused Taobao metadata IDs
    offset = 1_000_000
    tasks = []
    for cat in CATEGORY_CONFIGS:
        target = cat["target"]
        slice_items = tb_pylist[offset : offset + target]
        offset += target
        tasks.append((cat, slice_items))

    logging.info("Starting concurrent streaming for remaining categories...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_category, cat, items, conn_str) for cat, items in tasks]
        for f in futures:
            f.result()

    create_indexes(conn)

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM products;")
        total_p = cur.fetchone()[0]
        logging.info(f"PostgreSQL Total Products: {total_p:,}")

    sync_to_sqlite(conn)

    conn.close()
    logging.info("All tasks completed successfully!")


if __name__ == "__main__":
    main()
