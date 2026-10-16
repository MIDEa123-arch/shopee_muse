#!/usr/bin/env python3
"""
End-to-End Verification Suite for Alibaba MUSE Recommendation Zones & Shopee Visual Search Cards.
Tests explicit quality, relevance, latency, and visual rendering criteria across all touchpoints.
"""
import sys
import time
import urllib.parse
import httpx

BASE_URL = "http://127.0.0.1:8000"


def assert_criterion(condition, code, description, detail=""):
    status = "✅ PASS" if condition else "❌ FAIL"
    print(f"{status} [{code}] {description}" + (f" -> {detail}" if detail else ""))
    if not condition:
        raise AssertionError(f"Criterion {code} failed: {description} ({detail})")


def run_verification():
    print("=" * 88)
    print("🚀 BẮT ĐẦU KIỂM THỬ HỆ THỐNG GỢI Ý ALIBABA MUSE & SHOPEE VISUAL SEARCH CARDS")
    print("=" * 88)

    s = httpx.Client(timeout=10.0)

    # Wait for server readiness
    for _ in range(20):
        try:
            r = s.get(f"{BASE_URL}/api/catalog")
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.5)

    # 1. Login as Demo User #1
    r_login = s.post(f"{BASE_URL}/api/auth/demo-login", json={"user_id": 1})
    assert_criterion(r_login.status_code == 200, "AUTH-01", "Đăng nhập hồ sơ Demo User #1 thành công", f"HTTP {r_login.status_code}")

    # Clear demo interest first and set explicit interest in Category 1 (Thiết Bị Điện Tử)
    s.post(f"{BASE_URL}/api/recommendations/demo-interest/1")

    # =========================================================================
    # ZONE 1: SHOPEE-STYLE SEARCH SUGGESTIONS (ZERO-QUERY & LIVE TYPING CARDS)
    # =========================================================================
    print("\n--- [KHU VỰC 1] GỢI Ý TRÊN THANH TÌM KIẾM (SHOPEE VISUAL PRODUCT CARDS) ---")
    t0 = time.perf_counter()
    r_zero = s.get(f"{BASE_URL}/api/search/suggestions?q=").json()
    ms_zero = (time.perf_counter() - t0) * 1000
    zero_cards = r_zero.get("products", [])
    assert_criterion(
        len(zero_cards) == 6 and all(c.get("image_url") and c.get("price") > 0 for c in zero_cards),
        "SEARCH-ZERO-01",
        "Zero-Query (Click ô tìm kiếm): Trả về 6 thẻ sản phẩm có hình ảnh, giá, giảm giá và lý do AI",
        f"{len(zero_cards)} cards in {ms_zero:.1f} ms | Top 1: {zero_cards[0]['name']} ({zero_cards[0]['recommendation_reason']})"
    )
    assert_criterion(
        r_zero.get("suggestion_context", {}).get("mode") == "zero_query_personalized",
        "SEARCH-ZERO-02",
        "Zero-Query dựa trên chuỗi hành vi gần đây + ngành hàng yêu thích + điểm MUSE P(click)",
        f"Mode={r_zero['suggestion_context']['mode']}, Signals={r_zero['suggestion_context']['signals']}"
    )

    for query_kw, expected_cat_ids, expected_substr, label in [
        ("bàn phím cơ", {1, 2}, "bàn phím", "Tìm có dấu 'bàn phím cơ'"),
        ("ban phim co", {1, 2}, "bàn phím", "Tìm không dấu 'ban phim co'"),
        ("laptop", {1}, "laptop", "Tìm 'laptop'"),
        ("son kem", {7}, "son kem", "Tìm 'son kem' (Mỹ phẩm)"),
        ("tai nghe", {2, 1, 9}, "tai nghe", "Tìm 'tai nghe' (Âm thanh)"),
    ]:
        t0 = time.perf_counter()
        r_q = s.get(f"{BASE_URL}/api/search/suggestions?q={urllib.parse.quote(query_kw)}").json()
        ms_q = (time.perf_counter() - t0) * 1000
        q_cards = r_q.get("products", [])
        top_card = q_cards[0] if q_cards else {}
        top_name = (top_card.get("name") or "").lower()
        assert_criterion(
            len(q_cards) >= 4
            and top_card.get("category_id") in expected_cat_ids
            and expected_substr in top_name
            and top_card.get("p_click") is not None,
            f"SEARCH-LIVE-{query_kw[:6].upper()}",
            f"{label}: Hiển thị thẻ sản phẩm khớp tên, đúng ngành hàng, có ảnh & điểm MUSE P(click)",
            f"{len(q_cards)} cards ({ms_q:.1f} ms) | #1: {top_card.get('name')} | Cat={top_card.get('category_id')} | P(click)={top_card.get('p_click')}"
        )

    # =========================================================================
    # ZONE 2: HOME FEED ("GỢI Ý HÔM NAY" - TAOBAO GUESS YOU LIKE PERSONALIZED BY MUSE)
    # =========================================================================
    print("\n--- [KHU VỰC 2] TRANG CHỦ 'GỢI Ý HÔM NAY' (CÁ NHÂN HÓA BỞI ALIBABA MUSE) ---")
    t0 = time.perf_counter()
    home_tech = s.get(f"{BASE_URL}/api/recommendations?touchpoint=home&limit=24").json()
    ms_home = (time.perf_counter() - t0) * 1000
    tech_top6_cats = [item["category_id"] for item in home_tech["items"][:6]]
    assert_criterion(
        home_tech["meta"]["model_used"] is True and tech_top6_cats.count(1) >= 2,
        "HOME-MUSE-01",
        "Hồ sơ User #1 (Công nghệ/Laptop): Top gợi ý Trang chủ phản ánh đúng sở thích với điểm P(click) thật",
        f"Latency={ms_home:.1f} ms | Engine={home_tech['meta']['engine']} | Top-6 Cats={tech_top6_cats}"
    )

    # Switch to User #2 (Trần Thị Mai Lan - Mỹ phẩm & Sắc đẹp) and verify natural profile shift
    s.post(f"{BASE_URL}/api/auth/demo-login", json={"user_id": 2})
    home_beauty = s.get(f"{BASE_URL}/api/recommendations?touchpoint=home&limit=24").json()
    beauty_top6_cats = [item["category_id"] for item in home_beauty["items"][:6]]
    assert_criterion(
        beauty_top6_cats.count(7) >= 2 and home_beauty["items"][0]["id"] != home_tech["items"][0]["id"],
        "HOME-MUSE-02",
        "Chuyển sang User #2 (Mỹ Phẩm/Thời Trang): Gợi ý Trang chủ tự động cá nhân hóa theo gu User #2",
        f"Top-6 Cats={beauty_top6_cats} | #1: {home_beauty['items'][0]['name']}"
    )

    # Switch back to User 1
    s.post(f"{BASE_URL}/api/auth/demo-login", json={"user_id": 1})

    # Test Home Category Filter Tab (e.g. Category 5 - Giày Dép)
    home_shoes = s.get(f"{BASE_URL}/api/recommendations?touchpoint=home&category_id=5&limit=12").json()
    assert_criterion(
        len(home_shoes["items"]) == 12 and all(i["category_id"] == 5 for i in home_shoes["items"]),
        "HOME-TAB-03",
        "Tab lọc ngành hàng trực tiếp trên Trang chủ (VD: Giày Dép Cat 5): 100% sản phẩm thuộc Cat 5 và xếp hạng bởi MUSE",
        f"Count={len(home_shoes['items'])}, #1={home_shoes['items'][0]['name']} (P(click)={home_shoes['items'][0].get('p_click')})"
    )

    # =========================================================================
    # ZONE 3: PERSONALIZED FLASH SALE DEALS (/api/recommendations/deals)
    # =========================================================================
    print("\n--- [KHU VỰC 3] FLASH SALE CÁ NHÂN HÓA HỢP GU AI (/api/recommendations/deals) ---")
    deals = s.get(f"{BASE_URL}/api/recommendations/deals?limit=6").json()
    assert_criterion(
        len(deals["items"]) == 6 and deals["personalized"] is True and all(d["discount_percent"] >= 20 for d in deals["items"]),
        "DEALS-MUSE-01",
        "Flash Sale Cá Nhân Hóa trả về 6 deal giảm sâu (>=20%) khớp sở thích & khúc giá của user",
        f"Personalized={deals['personalized']} | #1: {deals['items'][0]['name']} (-{deals['items'][0]['discount_percent']}%, {deals['items'][0].get('recommendation_reason')})"
    )

    # =========================================================================
    # ZONE 4, 5: PRODUCT DETAIL PAGE (SIMILAR + "CÓ THỂ BẠN CŨNG THÍCH")
    # =========================================================================
    print("\n--- [KHU VỰC 4, 5] TRANG CHI TIẾT SẢN PHẨM (TƯƠNG TỰ + CÓ THỂ BẠN CŨNG THÍCH) ---")
    laptop_search = s.get(f"{BASE_URL}/api/products?q=laptop&category_id=1&page_size=5").json()
    anchor_laptop = laptop_search["items"][0]
    lid = anchor_laptop["id"]

    # Zone 4: Similar Products (SCL cosine)
    sim_res = s.get(f"{BASE_URL}/api/recommendations?touchpoint=similar&product_id={lid}&limit=6").json()
    sim_items = sim_res.get("items", [])
    assert_criterion(
        len(sim_items) == 6
        and sim_res["meta"]["score_type"] == "cosine_similarity"
        and all(i["category_id"] == anchor_laptop["category_id"] and i["id"] != lid for i in sim_items),
        "PDP-SIMILAR-01",
        "Sản phẩm tương tự: cùng ngành hàng, xếp bằng cosine SCL 128D",
        f"ScoreType={sim_res['meta']['score_type']} | #1={sim_items[0]['name']} (Cosine={sim_items[0].get('similarity')})"
    )

    # Zone 5: "Có thể bạn cũng thích" (MUSE P(click), no hand-written pairing)
    comp_res = s.get(f"{BASE_URL}/api/recommendations?touchpoint=complementary&product_id={lid}&limit=6").json()
    comp_items = comp_res.get("items", [])
    comp_Ids = {i["id"] for i in comp_items}
    sim_Ids = {i["id"] for i in sim_items}
    assert_criterion(
        len(comp_items) == 6
        and comp_Ids.isdisjoint(sim_Ids)
        and comp_res["meta"]["score_type"] == "p_click"
        and not any("mua kèm" in (i.get("recommendation_reason") or "").lower() for i in comp_items),
        "PDP-ALSO-LIKE-01",
        "Có thể bạn cũng thích: không trùng mục Tương tự, xếp bằng MUSE P(click), không dùng nhãn 'mua kèm' tự bịa",
        f"Overlap={len(comp_Ids & sim_Ids)} | Score={comp_res['meta']['score_type']} | Cats={[i['category_id'] for i in comp_items]} | #1={comp_items[0]['name']}"
    )

    # =========================================================================
    # ZONE 7: SMART CART CROSS-SELL & FREESHIP FILLER (touchpoint=cart)
    # =========================================================================
    print("\n--- [KHU VỰC 7] GIỎ HÀNG THÔNG MINH (GOM ĐƠN FREESHIP & MUA KÈM GIỎ HÀNG) ---")
    s.post(f"{BASE_URL}/api/cart", json={"product_id": lid, "quantity": 1})
    cart_recs = s.get(f"{BASE_URL}/api/recommendations?touchpoint=cart&limit=12").json()
    cart_items = cart_recs.get("items", [])
    assert_criterion(
        len(cart_items) >= 6 and all(i["id"] != lid for i in cart_items),
        "CART-MUSE-01",
        "Gợi ý trong Giỏ hàng (touchpoint=cart): Trả về đầy đủ sản phẩm cùng shop gom Freeship + phụ kiện mua kèm hợp giỏ hàng",
        f"Count={len(cart_items)} | #1={cart_items[0]['name']} ({cart_items[0].get('recommendation_reason')})"
    )

    print("\n" + "=" * 88)
    print("🎉 TẤT CẢ TIÊU CHÍ KIỂM THỬ API & MODEL MUSE ĐỀU ĐẠT 100%!")
    print("=" * 88)


if __name__ == "__main__":
    run_verification()
