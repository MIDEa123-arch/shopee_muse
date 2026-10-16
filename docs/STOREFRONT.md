> **Cập nhật gợi ý theo loại hàng — 16/10/2026:** giao diện hiện có bộ lọc ngữ cảnh, lọc thẻ trùng và ẩn mã sản phẩm khỏi màn mua sắm. Điểm MUSE giữ nguyên nhưng tập kết quả hiển thị đã thay đổi. Xem [CONTEXT_RECOMMENDATIONS.md](CONTEXT_RECOMMENDATIONS.md) cho quy tắc và kiểm thử mới. Nội dung bên dưới lưu mốc commerce trước lớp lọc này.

# Lumi commerce — 16/10/2026

Thay giao diện mã/hình học bằng một cửa hàng tiếng Việt có ảnh, tên, giá, danh mục, tìm kiếm và các chức năng mua sắm hiện có. Không huấn luyện lại hoặc sửa checkpoint. Bản này có lớp trình bày hàng hóa minh họa, không phải cửa hàng bán hàng/giao nhận thật.

## Dữ liệu và giới hạn

- Nguồn: snapshot metadata [DummyJSON](https://dummyjson.com/docs/products), 157 cặp tên/ảnh; tên được Việt hóa thủ công. Ảnh tải về dự án, tổng 1.353.882 byte, không cần mạng ngoài khi duyệt. Manifest có URL nguồn và SHA-256 từng ảnh. Không nhập review/rating/số đã bán mẫu để tạo bằng chứng xã hội giả.
- Tám ngành hàng hiển thị: Điện tử, Thời trang, Làm đẹp, Nhà cửa & Đời sống, Giày dép, Túi & Phụ kiện, Đồng hồ, Thể thao.
- `product_presentations` gắn 11.611 ID đã có vào các mẫu hiển thị. Chỉ 8.192 ID đầy đủ đặc trưng, còn hàng, được dùng làm ứng viên mới. 3.419 ID chỉ có trong lịch sử vẫn không xuất hiện ở feed mới.
- Phép gắn là xác định theo ID/nhóm, **không phải phục hồi ngành hàng Taobao hoặc diễn giải vector SCL**. Hai ID có thể cùng ảnh/tên, phân biệt bằng SKU. Không khử trùng ảnh hay thay thứ tự để làm danh sách trông tốt hơn.
- `products`, `muse_item_features`, `muse_user_features`, ID maps, lịch sử và checkpoint giữ nguyên. Giá/ảnh/tên/shop được gắn khi serialize, dùng thống nhất ở chi tiết, wishlist, giỏ, báo giá và đơn hàng. Đơn cũ giữ snapshot cũ.
- Giá mới là giá mô phỏng từ giá mẫu × 25.000, làm tròn nghìn; đây không phải tỷ giá hiện tại hoặc giá bán thật.
- Các thông báo “AI gợi ý” chỉ hiện khi API thực sự dùng model. Fallback bỏ nhãn AI. Thông số MUSE/P(click)/AUC/GAUC chỉ ở Lab; ý nghĩa tỷ lệ xếp đúng cặp 62,02% được giải thích trong modal AI, không gắn cho từng món.

Giữ nguyên điểm và thứ tự dự đoán **không xác nhận chất lượng gợi ý đối với hàng hóa trong ảnh minh họa**. Muốn đánh giá điều đó cần metadata thật khớp ID hoặc dữ liệu đánh giá của danh mục mới. Nguồn và giới hạn hiện ở thanh trải nghiệm, ghi chú danh mục, chi tiết và giải thích AI.

## Luồng người dùng

Trang chủ có banner sản phẩm, tám nhóm bằng ảnh, lựa chọn hồ sơ, feed AI và thêm giỏ nhanh. Gợi ý chính vẫn chấm đầy đủ 8.192 ứng viên theo batch 64 trên CPU. Bộ lọc ngành hàng chỉ thu hẹp ứng viên, giữ điểm checkpoint và thứ tự trong tập lọc. Chọn nhóm không tạo lịch sử giả.

Màn chi tiết có số lượng, mua ngay/thêm giỏ, yêu thích, mô tả và nguồn, đánh giá từ đơn đã giao và một dãy SCL riêng. Hoạt động gần đây gọn trong phần mở rộng, so sánh hai hồ sơ và trước/sau hành vi vẫn hoạt động. Không trình bày tần suất nhóm ẩn danh như sở thích hàng hóa đã biết.

Tìm kiếm hỗ trợ tên tiếng Việt không dấu, mã ID, danh mục và cửa hàng; autocomplete dùng tên hiển thị. Giá lọc/sắp xếp lấy đúng giá hiển thị. Giỏ/báo giá/đặt hàng dùng cùng metadata. Đã khôi phục đúng điều kiện voucher lần đầu/VIP sau khi mã voucher đổi tên ở lần chuyển dữ liệu trước.

Khi API gợi ý trả 503, trang chủ giữ phần cửa hàng và nút thử lại; cập nhật lỗi giữ danh sách cũ kèm thông báo. Gợi ý liên quan lỗi không chặn mua hàng. Giỏ/đơn tiếp tục hoạt động khi phần gợi ý phụ lỗi. Các response có guard theo người/route/request/modal để tránh ghi nhầm kết quả trả chậm.

## Kiểm chứng

`tests/test_storefront.py` tạo bản sao SQLite; xác minh việc cài presentation không đổi từng bảng được bảo vệ. So sánh khi bật/tắt presentation, xóa cache suy luận giữa hai lượt: cả **65.536 điểm** của 8 hồ sơ × 8.192 ứng viên bằng nhau tuyệt đối, ID/thứ tự/điểm của 60 gợi ý đầu mỗi hồ sơ không đổi. Kiểm tra cặp tên/ảnh, phân biệt raw category với display category, lọc/search/giá, điều kiện voucher và snapshot đơn hàng.

`tests/browser_storefront.py` kiểm tra tám hồ sơ, trạng thái AI/khách, so sánh hồ sơ, xem thêm ổn định, bộ lọc không tạo lịch sử, giới hạn số đo chất lượng, Lab, chi tiết/SCL/yêu thích/số lượng, giỏ/chọn hàng, đặt/hủy đơn, tìm kiếm/lọc giá/phân trang, tài khoản/địa chỉ/voucher, cold start, xử lý HTTP 503 và retry. Các màn home/feed/detail/catalog/cart/checkout được chụp và kiểm tra ở 320, 390, 768, 1440 px; không tràn ngang, không chữ Trung Quốc, không ảnh lỗi hoặc JavaScript page errors trong lượt hoàn tất.

Tất cả test ghi dữ liệu chạy trên bản sao riêng. Unit/model giới hạn cgroup 1600M RAM/128M swap; Chromium 512M/64M; trình gắn metadata 400M/32M và tối đa hai ảnh tải đồng thời. Một worker CPU, không reload, không train. Giới hạn cgroup không phải cam kết latency hay tải đồng thời production.

## Cài và tháo lớp trình bày

Chạy `scripts.build_storefront` trên DB native, sau đó restart server để nạp lại cache presentation. Script tự tạo bản backup SQLite trước khi gắn metadata; đường dẫn nằm trong `catalog_settings.storefront` và API `/catalog.presentation`. Chạy lặp cho kết quả ánh xạ giống nhau.

Muốn quay về giao diện nhận diện ID, sao lưu hiện trạng rồi xóa các hàng `product_presentations` và setting `storefront`, restart server. Không cần khôi phục toàn bộ DB, nên có thể giữ các đơn và tương tác phát sinh sau lúc cài.

## Kết quả hoàn tất

- Python: **58/58 PASS**, 39,456 giây, log `/tmp/lumi-unit-final.log`.
- Chromium commerce: **12 nhóm luồng PASS**, không JavaScript page errors, log `/tmp/lumi-browser-final.log`, ảnh/result `/tmp/lumi-preview/`. Bao gồm mua ngay giữ số lượng, trạng thái giao demo và đánh giá sau nhận hàng hiện lại ở chi tiết.
- Bản chính: smoke chỉ đọc PASS, model_ready=true, so sánh hai hồ sơ dùng AI, guest không bị tự đăng nhập; home 320/390/768/1440 px không tràn ngang. Kết quả `/tmp/lumi-preview/live-results.json`.
- Áp dụng vào DB chính có backup `data/backups/before-storefront-20261016-020604.db`. Audit xác nhận **24 bảng cũ giữ nguyên từng hàng**, SQLite quick_check=ok, không lỗi foreign key. SHA-256 cả hai checkpoint khớp trước thay đổi. Xem `storefront_verification.json`.
- Dừng toàn bộ server/browser kiểm thử; giữ server chính `shopee-taobao.service` trên port 8000, một worker, MemoryMax=1600M và MemorySwapMax=128M. Không có OOM trong service kiểm thử hoặc service chính ở lần kiểm tra memory.events. Mức sử dụng thay đổi theo cache và tải; không phải phép thử tải production.
