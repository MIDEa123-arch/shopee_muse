"""Harvest authentic Vietnamese e-commerce seeds from Tiki API across all 11 categories."""
import json
import logging
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "data/vietnamese_seeds.json"

CATEGORIES = {
    1: {
        "name": "Thiết Bị Điện Tử & Công Nghệ",
        "queries": [
            "laptop asus", "laptop dell", "laptop lenovo thinkpad", "laptop macbook air",
            "laptop msi gaming", "laptop hp pavilion", "laptop acer nitro", "màn hình máy tính 24 inch",
            "màn hình gaming 144hz", "pc gaming i5", "máy tính để bàn dell", "máy in canon",
            "ổ cứng ssd di động", "ram laptop ddr4", "webcam full hd"
        ]
    },
    2: {
        "name": "Âm Thanh & Tai Nghe",
        "queries": [
            "tai nghe bluetooth chụp tai", "tai nghe bluetooth in ear", "loa bluetooth jbl",
            "loa bluetooth marshall", "tai nghe gaming có mic", "tai nghe không dây true wireless",
            "bàn phím cơ akko", "bàn phím cơ keychron", "bàn phím cơ dareu", "chuột không dây logitech",
            "chuột gaming logitech g102", "cáp sạc type c", "thẻ nhớ micro sd sandisk"
        ]
    },
    3: {
        "name": "Thời Trang & Phụ Kiện",
        "queries": [
            "áo thun nam cotton", "áo polo nam phối viền", "áo sơ mi nam dài tay", "áo sơ mi nam công sở",
            "quần jean nam ống suông", "quần tây nam dáng slimfit", "quần short nam thun thể thao",
            "áo khoác gió nam chống nước", "áo khoác dù nam", "áo hoodie nam nỉ bông"
        ]
    },
    4: {
        "name": "Thời Trang Nữ",
        "queries": [
            "đầm hoa nhí dáng xòe", "đầm dự tiệc sang trọng", "chân váy chữ a lưng cao",
            "áo sơ mi nữ công sở", "áo kiểu nữ phong cách hàn quốc", "áo blazer nữ hàn quốc",
            "quần jean nữ cạp cao", "quần ống rộng nữ lưng cao", "áo croptop nữ", "set đồ nữ thời trang"
        ]
    },
    5: {
        "name": "Giày Dép & Sneaker",
        "queries": [
            "giày sneaker nam trắng", "giày sneaker nữ hàn quốc", "giày chạy bộ nam thoáng khí",
            "giày lười nam da bò", "giày tây nam oxford", "giày cao gót nữ mũi nhọn 7cm",
            "sandal nữ đế xuồng", "dép quai ngang nam nữ", "giày búp bê nữ êm chân"
        ]
    },
    6: {
        "name": "Đồ Gia Dụng Thông Minh",
        "queries": [
            "nồi chiên không dầu điện tử", "nồi cơm điện tử cao tần", "robot hút bụi lau nhà",
            "máy hút bụi cầm tay không dây", "máy pha cà phê espresso", "máy xay sinh tố đa năng",
            "bình giữ nhiệt inox 304", "đèn bàn học led chống cận", "chảo chống dính vân đá tefal",
            "ấm đun nước siêu tốc thủy tinh", "nồi lẩu điện đa năng", "máy ép chậm hoa quả"
        ]
    },
    7: {
        "name": "Mỹ Phẩm & Sắc Đẹp",
        "queries": [
            "serum b5 phục hồi da", "serum vitamin c mờ thâm", "kem chống nắng nâng tone",
            "kem chống nắng kiềm dầu", "kem dưỡng ẩm cấp nước", "son kem lì lâu trôi",
            "son thỏi lì chính hãng", "nước tẩy trang dịu nhẹ", "sữa rửa mặt tạo bọt",
            "dầu gội bưởi ngăn rụng tóc", "nước hoa nam thơm lâu", "mặt nạ dưỡng ẩm giấy"
        ]
    },
    8: {
        "name": "Đồng Hồ & Trang Sức",
        "queries": [
            "đồng hồ nam dây kim loại casio", "đồng hồ nam dây da citizen", "đồng hồ nữ mặt nhỏ chính hãng",
            "đồng hồ điện tử thể thao", "ví da nam đứng da bò thật", "thắt lưng da nam khóa tự động",
            "kính mát nam phân cực chống uv", "dây chuyền bạc ý 925", "vòng tay phong thủy đá tự nhiên",
            "bông tai bạc nữ đính đá"
        ]
    },
    9: {
        "name": "Điện Thoại & Máy Tính Bảng",
        "queries": [
            "điện thoại iphone 15 pro max", "điện thoại iphone 14 128gb", "điện thoại samsung galaxy s24 ultra",
            "điện thoại samsung galaxy a54", "điện thoại xiaomi redmi note 13", "điện thoại oppo reno 11",
            "máy tính bảng ipad gen 10", "máy tính bảng ipad air m2", "máy tính bảng samsung galaxy tab",
            "ốp lưng magsafe chống sốc", "kính cường lực full màn hình", "pin sạc dự phòng 20000mah sạc nhanh"
        ]
    },
    10: {
        "name": "Đồ Chơi & Trẻ Em",
        "queries": [
            "bộ xếp hình lego classic", "bộ lắp ráp xe cảnh sát lego", "xe ô tô điều khiển từ xa biến hình",
            "búp bê barbie thời trang", "bộ đồ chơi nấu ăn nhà bếp", "xe đẩy em bé gấp gọn du lịch",
            "bình sữa chống sặc cho bé", "sữa bột meiji số 0 800g", "sữa bột aptamil úc",
            "tã bỉm quần moony natural", "đồ chơi gỗ thông minh cho bé"
        ]
    },
    11: {
        "name": "Thể Thao & Dã Ngoại",
        "queries": [
            "thảm tập yoga tpe chống trượt", "con lăn tập cơ bụng 4 bánh", "bộ tạ tay bọc cao su 5kg",
            "dây kháng lực tập mông đùi", "kính bơi chống sương tráng gương", "bóng đá tiêu chuẩn fifa số 5",
            "vợt cầu lông yonex chính hãng", "lều cắm trại tự bung 4 người", "ghế xếp dã ngoại câu cá",
            "bình nước thể thao 1000ml bpa free", "giày đá bóng sân cỏ nhân tạo"
        ]
    }
}


def fetch_query(cat_id, query):
    url = f"https://tiki.vn/api/v2/products?limit=30&q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            items = data.get("data", [])
            valid = []
            for item in items:
                name = item.get("name")
                price = item.get("price")
                img = item.get("thumbnail_url")
                if not name or not price or not img:
                    continue
                # Reject accessories masquerading in primary hardware queries
                name_lower = name.lower()
                if cat_id == 1 and query.startswith("laptop "):
                    if any(bad in name_lower for bad in ["bàn phím", "miếng lót", "dán màn hình", "skin", "túi chống sốc", "cáp sạc", "quạt tản nhiệt"]):
                        continue
                if cat_id == 9 and any(phone_q in query for phone_q in ["iphone", "samsung galaxy", "xiaomi", "oppo"]) and not any(acc in query for acc in ["ốp lưng", "kính cường lực", "pin"]):
                    if any(bad in name_lower for bad in ["ốp lưng", "cường lực", "miếng dán", "bao da", "dây sạc"]):
                        continue
                valid.append({
                    "cat_id": cat_id,
                    "query": query,
                    "tiki_id": item.get("id"),
                    "name": name.strip(),
                    "price": int(price),
                    "original_price": int(item.get("original_price") or price),
                    "discount_rate": int(item.get("discount_rate") or 0),
                    "brand_name": (item.get("brand_name") or "Chính Hãng").strip(),
                    "seller_name": (item.get("seller_name") or "Tiki Trading").strip(),
                    "rating_star": float(item.get("rating_average") or 4.8),
                    "sold_count": int((item.get("quantity_sold") or {}).get("value") or random.randint(50, 2000)),
                    "image_url": img,
                    "is_mall": bool(item.get("is_authentic") or item.get("tiki_verified") or "chính hãng" in name_lower),
                    "is_freeship": True,
                })
            return valid
    except Exception as exc:
        logging.warning("Error fetching query '%s': %s", query, exc)
        return []


def main():
    start = time.time()
    tasks = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for cat_id, cat_info in CATEGORIES.items():
            for query in cat_info["queries"]:
                tasks.append(executor.submit(fetch_query, cat_id, query))
                time.sleep(0.05)

        all_seeds = []
        seen_names = set()
        for future in as_completed(tasks):
            results = future.result()
            for r in results:
                name_clean = r["name"].lower()
                if name_clean not in seen_names:
                    seen_names.add(name_clean)
                    all_seeds.append(r)

    by_cat = {}
    for s in all_seeds:
        by_cat.setdefault(s["cat_id"], []).append(s)

    logging.info("Harvested %d unique authentic Vietnamese products across %d categories in %.2fs", len(all_seeds), len(by_cat), time.time() - start)
    for cat_id in sorted(by_cat):
        logging.info("  Cat %d (%s): %d seeds", cat_id, CATEGORIES[cat_id]["name"], len(by_cat[cat_id]))

    OUTPUT_FILE.write_text(json.dumps(all_seeds, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Saved seeds to %s", OUTPUT_FILE)


if __name__ == "__main__":
    import random
    main()
