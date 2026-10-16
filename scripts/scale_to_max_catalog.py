"""Scale catalog to the absolute maximum of Taobao-MM dataset: 4,164,497 products.

Streams remaining ~3.16 million products from Amazon Reviews 2023 across 8 major domains:
  - Clothing_Shoes_and_Jewelry (+600k) -> Fashion & Shoes (Cat 3, 4, 5)
  - Home_and_Kitchen (+500k) -> Home & Smart Appliances (Cat 6)
  - Cell_Phones_and_Accessories (+400k) -> Phones & Accessories (Cat 9)
  - Beauty_and_Personal_Care (+350k) -> Cosmetics & Skincare (Cat 7)
  - Toys_and_Games (+350k) -> Toys & Children (Cat 10)
  - Sports_and_Outdoors (+300k) -> Sports & Outdoors (Cat 11)
  - Automotive (+300k) -> Vehicle & Tech Accessories (Cat 8)
  - Tools_and_Home_Improvement (+362k) -> Home Tools & Tech (Cat 6)

Total: 4,164,497 products (100% of authentic Taobao feature IDs).
"""
import json
import logging
import random
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
        "domain": "Clothing_Shoes_and_Jewelry",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Clothing_Shoes_and_Jewelry.jsonl",
        "cat_id": 3,
        "cat_name": "Thời Trang & Giày Dép",
        "target": 600_000,
    },
    {
        "domain": "Home_and_Kitchen",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Home_and_Kitchen.jsonl",
        "cat_id": 6,
        "cat_name": "Đồ Gia Dụng Thông Minh",
        "target": 500_000,
    },
    {
        "domain": "Cell_Phones_and_Accessories",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Cell_Phones_and_Accessories.jsonl",
        "cat_id": 9,
        "cat_name": "Điện Thoại & Phụ Kiện",
        "target": 400_000,
    },
    {
        "domain": "Beauty_and_Personal_Care",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Beauty_and_Personal_Care.jsonl",
        "cat_id": 7,
        "cat_name": "Mỹ Phẩm & Sắc Đẹp",
        "target": 350_000,
    },
    {
        "domain": "Toys_and_Games",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Toys_and_Games.jsonl",
        "cat_id": 10,
        "cat_name": "Đồ Chơi & Trẻ Em",
        "target": 350_000,
    },
    {
        "domain": "Sports_and_Outdoors",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Sports_and_Outdoors.jsonl",
        "cat_id": 11,
        "cat_name": "Thể Thao & Dã Ngoại",
        "target": 300_000,
    },
    {
        "domain": "Automotive",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Automotive.jsonl",
        "cat_id": 8,
        "cat_name": "Phụ Kiện Ô Tô Xe Máy",
        "target": 300_000,
    },
    {
        "domain": "Tools_and_Home_Improvement",
        "url": "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_Tools_and_Home_Improvement.jsonl",
        "cat_id": 6,
        "cat_name": "Dụng Cụ Sửa Chữa Nhà Cửa",
        "target": 362_406,
    },
]


def classify_title(domain, title):
    t = title.lower()
    if domain == "Clothing_Shoes_and_Jewelry":
        if any(w in t for w in ["shoe", "sneaker", "boot", "sandal", "giày", "dép"]):
            return "Giày dép thời trang " + title
        if any(w in t for w in ["dress", "skirt", "đầm", "váy"]):
            return "Thời trang nữ cao cấp " + title
        if any(w in t for w in ["shirt", "t-shirt", "polo", "jacket", "áo"]):
            return "Thời trang nam " + title
        if any(w in t for w in ["watch", "đồng hồ"]):
            return "Đồng hồ thời trang " + title
        return "Thời trang cao cấp " + title

    elif domain == "Home_and_Kitchen":
        if any(w in t for w in ["blender", "fryer", "cooker", "máy xay", "nồi"]):
            return "Thiết bị nhà bếp thông minh " + title
        if any(w in t for w in ["vacuum", "cleaner", "máy hút bụi", "robot"]):
            return "Robot hút bụi & Vệ sinh " + title
        if any(w in t for w in ["light", "lamp", "đèn"]):
            return "Đèn trang trí & Chiếu sáng " + title
        return "Đồ gia dụng tiện ích " + title

    elif domain == "Cell_Phones_and_Accessories":
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
        return "Phụ kiện điện thoại " + title

    elif domain == "Beauty_and_Personal_Care":
        if any(w in t for w in ["serum", "essence"]):
            return "Serum dưỡng da " + title
        if any(w in t for w in ["cream", "lotion", "kem"]):
            return "Kem dưỡng ẩm " + title
        if any(w in t for w in ["lipstick", "lip balm", "son"]):
            return "Son môi chính hãng " + title
        if any(w in t for w in ["sunscreen", "chống nắng"]):
            return "Kem chống nắng " + title
        return "Mỹ phẩm chăm sóc sắc đẹp " + title

    elif domain == "Toys_and_Games":
        if any(w in t for w in ["lego", "building block", "brick"]):
            return "Bộ xếp hình Lego " + title
        if any(w in t for w in ["figure", "action figure", "mô hình"]):
            return "Mô hình đồ chơi Anime/Action " + title
        if any(w in t for w in ["car", "vehicle", "rc", "xe"]):
            return "Xe điều khiển đồ chơi " + title
        return "Đồ chơi trẻ em thông minh " + title

    elif domain == "Sports_and_Outdoors":
        if any(w in t for w in ["gym", "fitness", "dumbbell"]):
            return "Dụng cụ tập Gym & Yoga " + title
        if any(w in t for w in ["camp", "tent", "lều"]):
            return "Lều cắm trại dã ngoại " + title
        if any(w in t for w in ["bottle", "flask", "bình nước"]):
            return "Bình nước thể thao " + title
        return "Dụng cụ thể thao dã ngoại " + title

    elif domain == "Automotive":
        if any(w in t for w in ["holder", "mount", "charger"]):
            return "Tẩu sạc & Giá đỡ ô tô " + title
        if any(w in t for w in ["camera", "dash cam"]):
            return "Camera hành trình ô tô " + title
        return "Phụ kiện & Chăm sóc xe hơi " + title

    elif domain == "Tools_and_Home_Improvement":
        if any(w in t for w in ["drill", "saw", "máy khoan"]):
            return "Máy khoan & Dụng cụ điện " + title
        if any(w in t for w in ["tool", "wrench", "kìm", "cờ lê"]):
            return "Bộ dụng cụ sửa chữa " + title
        return "Thiết bị & Dụng cụ nhà cửa " + title

    return title


def process_category(cat_cfg, taobao_items_slice, conn_str):
    domain = cat_cfg["domain"]
    url = cat_cfg["url"]
    target = cat_cfg["target"]
    cat_id = cat_cfg["cat_id"]

    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()

    logging.info(f"[{domain}] Starting stream for target {target:,} products...")

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
                        total_inserted += len(batch)
                        batch = []
                        if total_inserted % 25000 == 0:
                            logging.info(f"[{domain}] Inserted {total_inserted:,} / {target:,}...")

                    if total_inserted >= target:
                        break

                except Exception as e:
                    conn.rollback()
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

        logging.info(f"[{domain}] Finished! Total inserted this run: {total_inserted:,}")

    except Exception as e:
        conn.rollback()
        logging.exception(f"[{domain}] Stream failure: {e}")
    finally:
        cur.close()
        conn.close()


def main():
    conn_str = "dbname=shopee_muse user=midea"
    conn = psycopg2.connect(conn_str)

    logging.info("Loading Taobao item features from Parquet...")
    tb_table = pq.read_table(PARQUET_FILE, columns=["205", "206", "213", "214"])
    tb_pylist = tb_table.to_pylist()
    total_available = len(tb_pylist)
    logging.info(f"Loaded {total_available:,} authentic Taobao metadata references.")

    # Offset to 1,002,091 so remaining 3.16 million items are 100% disjoint & fresh
    offset = 1_002_091
    tasks = []
    for cat in CATEGORY_CONFIGS:
        target = cat["target"]
        slice_items = tb_pylist[offset : offset + target]
        offset += target
        tasks.append((cat, slice_items))

    logging.info(f"Starting concurrent scaling across {len(tasks)} categories to reach 4,164,497...")
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(process_category, cat, items, conn_str) for cat, items in tasks]
        for f in futures:
            f.result()

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM products;")
        total_p = cur.fetchone()[0]
        logging.info(f"POSTGRESQL SCALED TO: {total_p:,} PRODUCTS!")

    conn.close()
    logging.info("Scaling completed successfully!")


if __name__ == "__main__":
    main()
