"""Download curated Unsplash photos per product sub-type and assign them accurately.
Ensures:
- Vacuum/robot -> vacuum cleaner photos
- T-shirts/Shirts -> clothing photos
- Laptops/Keyboards -> tech photos
- Shoes -> footwear photos
- Air fryers/Coffee makers -> kitchen appliance photos
- Dresses/Skirts -> women fashion photos
- Skincare/Lipstick -> beauty photos
- Watches/Glasses -> accessory photos
- Multiple distinct photos per category/sub-type
- Never assign human face profile avatars to products!
"""
import concurrent.futures
import hashlib
import json
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config

# Curated Unsplash photo IDs by specific product type
UNSPLASH_CATALOG = {
    # 1. Electronics
    'laptop': [
        'photo-1588872657578-7efd1f1555ed', 'photo-1603302576837-37561b2e2302',
        'photo-1496181133206-80ce9b88a853', 'photo-1517336714731-489689fd1ca8'
    ],
    'keyboard': [
        'photo-1587829741301-dc798b83add3', 'photo-1618384887929-16ec33fab9ef',
        'photo-1595225476474-87563907a212', 'photo-1560762484-813fc97650a0'
    ],
    'mouse': [
        'photo-1527864550417-7fd91fc51a46', 'photo-1615663245857-ac93bb7c39e7',
        'photo-1626218174358-7769486c4b79'
    ],
    'monitor': [
        'photo-1527443224154-c4a3942d3acf', 'photo-1585792180666-f7347c490ee2',
        'photo-1547658719-da2b51169166'
    ],
    'charger': [
        'photo-1583863788434-e58a36330cf0', 'photo-1622445262464-84b1456045b6',
        'photo-1585338107529-13afc5f02586'
    ],
    'tech_acc': [
        'photo-1588872657578-7efd1f1555ed', 'photo-1597872200969-2b65d56bd16b',
        'photo-1527443224154-c4a3942d3acf'
    ],

    # 2. Audio
    'earbuds': [
        'photo-1590658268037-6bf12165a8df', 'photo-1606220588913-b3aacb4d2f46',
        'photo-1572536147248-ac59a8abfa4b'
    ],
    'headphone': [
        'photo-1546435770-a3e426bf472b', 'photo-1505740420928-5e560c06d30e',
        'photo-1484704849700-f032a568e944'
    ],
    'speaker': [
        'photo-1608043152269-423dbba4e7e1', 'photo-1545454675-3531b543be5d',
        'photo-1508700115892-45ecd05ae2ad'
    ],
    'mic': [
        'photo-1590658268037-6bf12165a8df', 'photo-1583795128727-6ec3642408f8'
    ],

    # 3. Men Fashion
    'men_tshirt': [
        'photo-1521572267360-ee0c2909d518', 'photo-1583743814966-8936f5b7be1a',
        'photo-1562157873-818bc0726f68'
    ],
    'men_shirt': [
        'photo-1602810318383-e386cc2a3ccf', 'photo-1596755094514-f87e34085b2c',
        'photo-1607345366928-199ea26cfe3e'
    ],
    'men_jacket': [
        'photo-1544441893-675973e31985', 'photo-1556905055-8f358a7a47b2',
        'photo-1509551388413-e18d0ac5d495'
    ],
    'men_pants': [
        'photo-1552902865-b72c031ac5ea', 'photo-1624378439575-d8705ad7ae80',
        'photo-1542272604-780c96856592'
    ],

    # 4. Women Fashion
    'women_dress': [
        'photo-1595777457583-95e059d581b8', 'photo-1572804013309-59a88b7e92f1',
        'photo-1515372039744-b8f02a3ae446'
    ],
    'women_top': [
        'photo-1598554747436-c9293d6a588f', 'photo-1534126511673-b6899657816a'
    ],
    'women_skirt': [
        'photo-1583496661160-fb5886a0aaaa', 'photo-1577900232427-18219b9166a0'
    ],
    'women_suit': [
        'photo-1515886657613-9f3515b0c78f', 'photo-1584273143981-41c073dfe8f8'
    ],

    # 5. Shoes
    'sneaker': [
        'photo-1542291026-7eec264c27ff', 'photo-1560769629-975ec94e6a86',
        'photo-1595950653106-6c9ebd614d3a', 'photo-1607522370275-f14206abe5d3'
    ],
    'sandal': [
        'photo-1603808033192-082d6919d3e1', 'photo-1562273138-f46be4ebdf33'
    ],
    'leather_shoe': [
        'photo-1533867617858-e7b97e060509', 'photo-1614252235316-8c857d38b5f4'
    ],
    'heels': [
        'photo-1543163521-1bf539c55dd2', 'photo-1535043934128-cf0b28d52f95'
    ],

    # 6. Appliances
    'vacuum': [
        'photo-1518640467707-6811f4a6ab73', 'photo-1558317374-067fb5f30001'
    ],
    'air_fryer': [
        'photo-1584269600464-37b1b58a9fe7', 'photo-1626082927389-6cd097cdc6ec'
    ],
    'coffee_maker': [
        'photo-1517668808822-9ebb02f2a0e6', 'photo-1514432324607-a09d9b4aefdd',
        'photo-1570968915860-54d5c301fa9f'
    ],
    'blender': [
        'photo-1570222094114-d054a817e56b'
    ],
    'fan': [
        'photo-1618941716939-553df3c6c278'
    ],

    # 7. Beauty
    'serum': [
        'photo-1620916566398-39f1143ab7be', 'photo-1608248597359-05a96a323381',
        'photo-1617897903246-719242758050'
    ],
    'sunscreen': [
        'photo-1556228720-195a672e8a03', 'photo-1571781926291-c477ebfd024b'
    ],
    'lipstick': [
        'photo-1586495777744-4413f21062fa', 'photo-1512496015851-a90fb38ba796'
    ],

    # 8. Accessories
    'watch': [
        'photo-1524805444758-089113d48a6d', 'photo-1522335789203-aabd1fc54bc9',
        'photo-1523275335684-37898b6baf30'
    ],
    'sunglasses': [
        'photo-1511499767150-a48a237f0083', 'photo-1572635196237-14b3f281503f'
    ],
    'wallet': [
        'photo-1627123424574-724758594e93', 'photo-1606503825008-909a67e75440'
    ]
}

KEYWORD_RULES = [
    # Appliances
    (['hút bụi', 'robot'], 'vacuum'),
    (['nồi chiên'], 'air_fryer'),
    (['cà phê'], 'coffee_maker'),
    (['xay', 'ép chậm'], 'blender'),
    (['quạt'], 'fan'),
    (['nồi cơm', 'áp suất', 'bếp', 'chảo', 'nồi', 'ấm đun', 'bàn là', 'lò nướng', 'ấm'], 'air_fryer'),

    # Electronics
    (['laptop', 'macbook'], 'laptop'),
    (['bàn phím', 'keychron', 'switch'], 'keyboard'),
    (['chuột', 'mouse'], 'mouse'),
    (['màn hình', 'screen', 'monitor'], 'monitor'),
    (['sạc', 'cáp', 'pin dự phòng', 'adapter'], 'charger'),
    (['hub', 'ssd', 'thẻ nhớ', 'usb', 'router', 'wifi', 'tai nghe gaming'], 'tech_acc'),

    # Audio
    (['tai nghe bluetooth', 'tws', 'airpods', 'không dây'], 'earbuds'),
    (['chụp tai', 'headphone', 'chống ồn', 'kiểm âm', 'tai nghe', 'dac'], 'headphone'),
    (['loa', 'soundbar'], 'speaker'),
    (['micro', 'thu âm', 'mic'], 'mic'),

    # Men
    (['áo polo', 'áo thun'], 'men_tshirt'),
    (['sơ mi nam', 'sơ mi'], 'men_shirt'),
    (['khoác', 'bomber', 'hoodie', 'blouson'], 'men_jacket'),
    (['quần', 'jogger', 'short', 'kaki', 'jean', 'đũi'], 'men_pants'),
    (['nam'], 'men_tshirt'),

    # Women
    (['đầm', 'váy', 'maxi'], 'women_dress'),
    (['áo kiểu', 'áo sơ mi nữ', 'croptop', 'cardigan', 'áo nữ'], 'women_top'),
    (['chân váy'], 'women_skirt'),
    (['set', 'blazer', 'dạ', 'nữ'], 'women_suit'),

    # Shoes
    (['sneaker', 'chạy bộ', 'thể thao'], 'sneaker'),
    (['dép', 'sandal', 'sục'], 'sandal'),
    (['giày lười', 'giày tây', 'da bò', 'oxford', 'boots', 'giày'], 'leather_shoe'),
    (['cao gót', 'búp bê'], 'heels'),

    # Beauty
    (['serum', 'tinh chất'], 'serum'),
    (['chống nắng'], 'sunscreen'),
    (['son'], 'lipstick'),
    (['kem', 'dưỡng', 'tẩy trang', 'sữa rửa mặt', 'toner', 'nước hoa hồng', 'mặt nạ', 'xịt khoáng', 'dung dịch', 'nước cân bằng'], 'serum'),

    # Accessories
    (['đồng hồ', 'band'], 'watch'),
    (['kính'], 'sunglasses'),
    (['ví', 'bóp', 'thắt lưng', 'balo', 'túi'], 'wallet'),
]

CATEGORY_FALLBACK = {
    1: 'tech_acc', 2: 'speaker', 3: 'men_tshirt', 4: 'women_dress',
    5: 'sneaker', 6: 'air_fryer', 7: 'serum', 8: 'watch'
}

CATEGORY_SUBTYPES = {
    1: {'laptop','keyboard','mouse','monitor','charger','tech_acc'},
    2: {'earbuds','headphone','speaker','mic'},
    3: {'men_tshirt','men_shirt','men_jacket','men_pants'},
    4: {'women_dress','women_top','women_skirt','women_suit'},
    5: {'sneaker','sandal','leather_shoe','heels'},
    6: {'vacuum','air_fryer','coffee_maker','blender','fan'},
    7: {'serum','sunscreen','lipstick'},
    8: {'watch','sunglasses','wallet'},
}


def has_keyword(name,keyword):
    """Match a complete word/phrase so `ấm` does not accidentally match `chấm`."""
    return re.search(rf'(?<!\w){re.escape(keyword)}(?!\w)',name,re.UNICODE) is not None


def download_all_images():
    img_dir = config.ROOT / 'static/images/catalog'
    img_dir.mkdir(parents=True, exist_ok=True)
    all_photo_ids = set()
    for ids in UNSPLASH_CATALOG.values():
        all_photo_ids.update(ids)

    photo_map = {}
    sources_path = img_dir / 'sources.json'
    sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}

    def fetch(pid):
        base_url = f"https://images.unsplash.com/{pid}"
        filename = hashlib.sha256(base_url.encode()).hexdigest()[:16] + '.jpg'
        target = img_dir / filename
        local_path = f"/static/images/catalog/{filename}"
        if not target.exists():
            url = f"{base_url}?auto=format&fit=crop&w=650&q=82&fm=jpg"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (ShopeeMUSE/2.0)'})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                target.write_bytes(data)
        return pid, local_path, base_url

    print(f"Downloading/verifying {len(all_photo_ids)} curated product images...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, pid) for pid in all_photo_ids]
        for f in concurrent.futures.as_completed(futures):
            try:
                pid, local_path, base_url = f.result()
                photo_map[pid] = local_path
                sources[base_url] = local_path
            except Exception as e:
                print(f"Error fetching {f}: {e}")

    sources_path.write_text(json.dumps(sources, indent=2))
    return photo_map


def assign_images(photo_map):
    db_path = config.DB_PATH
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    products = cur.execute('SELECT id, name, category_id FROM products').fetchall()
    print(f"Updating image_url for {len(products)} products...")

    # Map sub-type to local paths
    subtype_paths = {}
    for stype, pids in UNSPLASH_CATALOG.items():
        valid_paths = [photo_map[p] for p in pids if p in photo_map]
        if valid_paths:
            subtype_paths[stype] = valid_paths

    updates = []
    for pid, name, cat_id in products:
        name_lower = name.lower()
        sub = None
        allowed = CATEGORY_SUBTYPES.get(cat_id,set())
        for kws, target_type in KEYWORD_RULES:
            if target_type in allowed and any(has_keyword(name_lower,k) for k in kws):
                sub = target_type
                break
        if not sub or sub not in subtype_paths:
            sub = CATEGORY_FALLBACK.get(cat_id, 'tech_acc')

        pool = subtype_paths.get(sub, subtype_paths.get('tech_acc', []))
        # Deterministic choice based on product ID to ensure stability and variety
        chosen_img = pool[pid % len(pool)]
        updates.append((chosen_img, pid))

    cur.executemany('UPDATE products SET image_url=? WHERE id=?', updates)
    con.commit()
    print(f"Successfully updated {len(updates)} products with accurate matching images!")

    # Verify sample
    samples = cur.execute('''
        SELECT id, name, image_url FROM products
        WHERE name LIKE '%Hút Bụi%' OR name LIKE '%Áo%' OR name LIKE '%Giày%' OR name LIKE '%Nồi Chiên%' OR name LIKE '%Bàn Phím%'
        LIMIT 10
    ''').fetchall()
    print("\nVerified Samples:")
    for s in samples:
        print(f"[{s[0]}] {s[1][:45]:45s} -> {s[2]}")


if __name__ == '__main__':
    pmap = download_all_images()
    assign_images(pmap)
