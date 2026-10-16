"""Align Taobao source_category_id (col 206) 1-to-1 with Vietnamese category_id and product templates.

This ensures that:
1. Every Taobao category (source_category_id) maps deterministically to ONE Vietnamese category_id
   and ONE specific product template (e.g., all items in a given Taobao category are Laptops, or all are
   Headphones, or all are Lipsticks).
2. MUSE's 128D SCL multimodal embeddings and category embeddings (151_2_180 / 206) align with the
   Vietnamese categories and product kinds displayed in the UI.
3. All artificial 'demo_interest' rows are removed from user_behavior_history.
"""
import json
import random
import sqlite3
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config
from app.database import VERIFIED_CATEGORY_IMAGES
from scripts.build_vietnamese_catalog import PRODUCT_TEMPLATES, PROVINCES

# Map dominant Taobao categories from the 8 demo users' real histories to distinct Vietnamese categories
PINNED_TAOBAO_CATS = {
    # User 1 -> Cat 1 (Laptop & Máy tính) & Cat 2 (Âm thanh & Phụ kiện)
    "-2380521471790345789": (1, 0),
    "8678353119635898864": (1, 1),
    "-3701269066261102898": (2, 0),
    "-4017436308695531269": (2, 2),
    "-2352162164107185503": (1, 2),
    # User 2 -> Cat 7 (Mỹ phẩm & Sắc đẹp) & Cat 4 (Thời trang nữ)
    "-7860817872319999162": (7, 0),
    "-5525315372704820882": (7, 2),
    "-8162573606926791198": (4, 0),
    "8663989862059910184": (7, 1),
    "-3611486509900073399": (4, 1),
    # User 3 -> Cat 5 (Giày dép) & Cat 3 (Thời trang nam)
    "-4823507731448378248": (5, 0),
    "4126510408659497178": (5, 1),
    "5729535529744443877": (3, 0),
    "8523587317571757109": (3, 1),
    "-5374407675500058408": (5, 2),
    # User 4 -> Cat 6 (Nhà cửa & Đời sống) & Cat 10 (Đồ chơi & Mẹ bé)
    "2421902788023766924": (6, 0),
    "-4254409368053245634": (6, 1),
    "-9006272157955270177": (10, 0),
    "1792450202834823192": (6, 2),
    # User 5 -> Cat 4 (Thời trang nữ) & Cat 8 (Phụ kiện & Đồng hồ)
    "825326402737907891": (4, 2),
    "1393050267716729270": (8, 0),
    "-5175347256573863316": (4, 0),
    "8466927054711127767": (8, 1),
    # User 6 -> Cat 11 (Thể thao & Dã ngoại)
    "-2504781601662852770": (11, 0),
    "4581416561711324718": (11, 1),
    "3842000326276083354": (11, 2),
    "-1570566781992170732": (11, 0),
    # User 7 -> Cat 7 (Mỹ phẩm)
    "-2032629835927058410": (7, 3),
    "2852473740901742219": (7, 1),
    "-5452758334325761963": (7, 2),
    # User 8 -> Cat 9 (Điện thoại & Tablet)
    "-3066197207802889811": (9, 0),
    "285377220712370953": (9, 1),
    "-4231985838156467911": (9, 2),
    "-4236311974443023908": (2, 1),
}


def resolve_cat_and_template(source_cat_str: str):
    if source_cat_str in PINNED_TAOBAO_CATS:
        cat_id, tpl_idx = PINNED_TAOBAO_CATS[source_cat_str]
        tpl_list = PRODUCT_TEMPLATES[cat_id]
        return cat_id, tpl_list[tpl_idx % len(tpl_list)]
    try:
        val = abs(int(source_cat_str))
    except Exception:
        val = abs(hash(source_cat_str))
    cat_id = (val % 11) + 1
    tpl_list = PRODUCT_TEMPLATES[cat_id]
    tpl = tpl_list[(val // 11) % len(tpl_list)]
    return cat_id, tpl


def build_product_fields(prod_id: int, source_cat_str: str, rng: random.Random):
    cat_id, tpl = resolve_cat_and_template(source_cat_str)
    brand = tpl["brand"]
    line = tpl["lines"][prod_id % len(tpl["lines"])]
    spec = tpl["specs"][(prod_id // len(tpl["lines"])) % len(tpl["specs"])]
    color = tpl["colors"][(prod_id // 7) % len(tpl["colors"])]

    img_pool = VERIFIED_CATEGORY_IMAGES[cat_id]
    img_url = img_pool[prod_id % len(img_pool)]

    prefix = ""
    low_line = line.lower()
    if cat_id == 1 and not (low_line.startswith("laptop") or low_line.startswith("macbook") or low_line.startswith("màn hình")):
        prefix = "Laptop "
    elif cat_id == 9 and not (low_line.startswith("điện thoại") or low_line.startswith("máy tính bảng") or low_line.startswith("apple") or low_line.startswith("samsung") or low_line.startswith("củ sạc") or low_line.startswith("pin")):
        prefix = "Điện thoại "

    name = f"{prefix}{line} ({spec}) - {color}"
    if len(name) > 160:
        name = name[:157] + "..."

    base_p = tpl["base_price"]
    factor = 0.86 + ((prod_id % 19) * 0.022)
    price = round(int(base_p * factor), -3)
    discounts = [0, 5, 10, 15, 20, 25, 30, 35, 40, 50]
    discount = discounts[prod_id % len(discounts)]
    orig_price = round(int(price / (1 - discount / 100)), -3) if discount > 0 else price

    prov_id, prov_name, shops = PROVINCES[prod_id % len(PROVINCES)]
    shop_name = f"{brand} {shops[prod_id % len(shops)]}" if (prod_id % 3 != 0) else shops[prod_id % len(shops)]

    return (
        name,
        cat_id,
        price,
        orig_price,
        discount,
        img_url,
        prov_id,
        shop_name,
        tpl["desc"],
        brand,
        json.dumps([img_url]),
    )


def main():
    t0 = time.time()
    db = sqlite3.connect(config.DB_PATH)
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA synchronous = NORMAL")

    # 1. Remove all artificial demo_interest rows
    deleted = db.execute("DELETE FROM user_behavior_history WHERE action_type = 'demo_interest'").rowcount
    print(f"Removed {deleted} artificial demo_interest rows from user_behavior_history.")

    # 2. Fetch all active products (id <= 100000 OR referenced in muse_item_features / user_behavior_history / cart_items / order_items)
    rows = db.execute("""
        SELECT id, source_category_id FROM products
        WHERE id <= 100000
           OR raw_item_id IN (SELECT raw_item_id FROM muse_item_features)
           OR id IN (SELECT product_id FROM user_behavior_history WHERE product_id IS NOT NULL)
           OR id IN (SELECT product_id FROM cart_items)
           OR id IN (SELECT product_id FROM order_items)
    """).fetchall()
    print(f"Aligning {len(rows):,} products with their Taobao source_category_id...")

    rng = random.Random(42)
    updates = []
    for prod_id, source_cat in rows:
        fields = build_product_fields(prod_id, str(source_cat or "0"), rng)
        updates.append((*fields, prod_id))

    db.executemany("""
        UPDATE products
        SET name = ?,
            category_id = ?,
            price = ?,
            original_price = ?,
            discount_percent = ?,
            image_url = ?,
            province_id = ?,
            shop_name = ?,
            description = ?,
            brand = ?,
            images_json = ?
        WHERE id = ?
    """, updates)

    # 3. Also clean old live click/cart history that had mismatched categories and seed clean natural history per demo user
    # Keep imported_click untouched; align live click/cart/favorite rows to match each user's top categories
    db.execute("DELETE FROM user_behavior_history WHERE action_type IN ('click', 'add_to_cart', 'favorite')")
    user_primary_cats = {
        1: [1, 2],
        2: [7, 4],
        3: [5, 3],
        4: [6, 10],
        5: [4, 8],
        6: [11, 5],
        7: [7, 4],
        8: [9, 2],
    }
    for uid, cats in user_primary_cats.items():
        urow = db.execute("SELECT raw_user_id FROM users WHERE id = ?", (uid,)).fetchone()
        raw_uid = urow[0] if urow and urow[0] else str(uid)
        for cid in cats:
            prods = db.execute(
                "SELECT id, raw_item_id FROM products WHERE id <= 20000 AND category_id = ? ORDER BY sold_count DESC LIMIT 4",
                (cid,)
            ).fetchall()
            for idx, (pid, raw_id) in enumerate(prods):
                act = "add_to_cart" if idx == 0 else "click"
                db.execute(
                    "INSERT INTO user_behavior_history(user_id, raw_user_id, product_id, raw_item_id, action_type) VALUES (?, ?, ?, ?, ?)",
                    (uid, raw_uid, pid, raw_id, act)
                )

    db.commit()
    db.close()
    print(f"Done in {time.time() - t0:.2f}s!")


if __name__ == "__main__":
    main()
