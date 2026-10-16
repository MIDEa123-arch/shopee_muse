> **Giao diện hiện tại — Lumi commerce, 16/10/2026:** ảnh/tên tiếng Việt được gắn qua bảng hiển thị riêng; giữ nguyên điểm và thứ tự model. Xem [STOREFRONT.md](STOREFRONT.md) cho luồng commerce, giới hạn ngữ nghĩa, kiểm chứng và cách chạy. Các mô tả giao diện mã/hình học bên dưới là lịch sử trước commerce.

# Demo thể hiện cá nhân hóa — 16/10/2026

Mục tiêu của lượt này là làm rõ dữ liệu đầu vào và hành vi gợi ý trên giao diện, mở rộng lựa chọn đúng miền Taobao, giữ nguyên năng lực checkpoint đã học. Không huấn luyện lại, không đổi ID maps, không tăng chỉ số AUC bằng thay đổi cách hiển thị.

## Dữ liệu mới

`expand_taobao_catalog.py` đọc bốn trường 205/206/213/214 từ parquet gốc, batch 32.768, `use_threads=False`. Lấy mẫu xác định bằng hash ID và reservoir giới hạn theo nhóm; lấp các nhóm thưa trước, phần còn lại dành cho nhóm xuất hiện nhiều trong tám lịch sử gốc. Chỉ nhập ID có cả vocabulary checkpoint và SCL embedding. Không tạo thêm hành vi hay hồ sơ giả.

- Thêm **5.989** ID với đặc trưng từ nguồn, nâng tập ứng viên từ 2.203 lên **8.192**.
- Giữ đủ 5.622 ID ban đầu và các features cũ; tổng products/muse_item_features **11.611**.
- **1.269 nhóm** có ứng viên, trong đó **1.256 nhóm có ít nhất 6 mẫu**; nhóm chỉ một mẫu giảm từ 614 xuống **2**.
- 3.419 ID chỉ có trong lịch sử vẫn giữ trạng thái thiếu item features, không dùng làm ứng viên mới.
- Giữ mã và nhóm tiếng Việt, hình nhận diện theo ID. Màu theo nhóm nhất quán giúp tìm lại nhóm; hình không mô tả hoặc khôi phục hàng hóa gốc.
- Giá và giao nhận của mẫu thêm mới là mô phỏng, được ghi rõ trong trải nghiệm mua thử.

Script tự backup SQLite ngay trước transaction, ghi đường dẫn vào `catalog_settings.expansion_backup`, chạy lặp an toàn. Các dữ liệu người dùng, giỏ, đơn và lịch sử thật không được thay đổi bởi script.

## Xếp hạng và giải thích

Vẫn chấm toàn bộ 8.192 ứng viên trên CPU, theo lô 64, sắp xếp điểm checkpoint giảm dần. Không rút còn một prefix ảnh/shop/giá hoặc cộng điểm theo nhóm minh họa. Cache theo model, database, user, tập ứng viên và hành vi thật; tối đa tám khóa, 300 giây.

Trang chủ loại mẫu đã có trong chuỗi gốc và 1.000 hành vi thật gần nhất. Đây là quy tắc khám phá mới, không phải thay trọng số. Tìm kiếm vẫn cho phép tìm lại những mẫu đó. Những hàng xóm SCL của mẫu vừa xem xuất hiện trong khối riêng, không trộn cosine vào P(click).

`GET /recommendations/experience` chỉ báo dữ liệu của người đang đăng nhập: số lượt gốc, số tương tác web, nhóm xuất hiện nhiều, ví dụ thật từ chuỗi và sáu hành vi gần nhất. Khách chưa đăng nhập nhận kết quả rỗng. Tần suất nhóm không được trình bày như attribution/độ đóng góp nhân quả của model.

`GET /recommendations/compare-profiles` chỉ hoạt động khi bật DEMO_MODE và chỉ nhận ID hồ sơ có `muse_user_features`. Hai danh sách dùng cùng checkpoint/tập ứng viên, lọc mẫu từng xem riêng từng người. Trả số phần tử trùng của 12 gợi ý đầu, hiển thị sáu thẻ mỗi bên. Endpoint không tạo phiên, không đổi người đăng nhập, không ghi behavior/recommendation logs và không sửa metrics phiên đang xem. Nếu model không dùng được, giao diện ghi rõ fallback và không kết luận về cá nhân hóa.

## Trải nghiệm quan sát được

- Bắt đầu bằng một trong tám hồ sơ tiếng Việt hoặc xem so sánh hai hồ sơ ngay khi chưa đăng nhập.
- Xem tần suất nhóm trong lịch sử gốc, ví dụ thật đã từng xuất hiện, và timeline các thao tác thật.
- Sau xem/lưu/thêm giỏ, so sánh 12 gợi ý đầu của cùng người/cùng bộ lọc: số mẫu mới, mẫu đổi vị trí và ảnh trước/sau. Không ép có số thay đổi lớn.
- Ghi rõ thay đổi do lịch sử và việc bỏ qua mẫu đã xem, không gọi đó là % chính xác hay huấn luyện trực tuyến.
- Khối tiếp nối từ mẫu vừa xem dùng đặc trưng SCL, tách khỏi feed checkpoint chính.
- Lỗi refresh giữ danh sách cũ, có thông báo và nút thử lại. Guard theo user/route/request/modal ngăn response cũ cập nhật sai người hoặc màn hình. Không ghi nhãn AI cho danh mục fallback.
- Giữ tìm kiếm, nhóm, wishlist, giỏ, mua ngay/mua thử, đặt/hủy đơn và Lab.

## Kiểm chứng và bộ nhớ

**53 kiểm thử Python: PASS** (`/tmp/taobao-experience-unit.log`, 19,01 giây), gồm toàn bộ hợp đồng thương mại cũ và các kiểm tra native. Có kiểm thử riêng cho tần suất nhóm khớp chuỗi nguồn, không lộ lịch sử cho guest, loại mẫu đã xem mà giữ điểm checkpoint, so sánh chỉ đọc và giới hạn hồ sơ/demo mode.

**Chromium native: PASS** (`/tmp/taobao-experience-browser-final.log`): đủ tám hồ sơ, AI badges/quality/Lab, tìm kiếm và pagination, wishlist, giỏ/chọn hàng, checkout, đặt/hủy đơn, địa chỉ, cold start, lỗi model/API và layout home/feed/detail/catalog/cart/checkout ở 320/390/768/1440 px.

**Chromium experience: PASS** (`/tmp/taobao-experience-evidence.log`): so sánh hai hồ sơ không đăng nhập/không đổi phiên, đổi chọn hồ sơ trong modal, số lượt nhóm đúng API, số mẫu mới trước/sau khớp kết quả thật, mẫu đã xem rời feed, hàng xóm gần đây, HTTP 503 khi refresh và retry phục hồi đúng phép so sánh. Modal/khối bằng chứng không tràn ngang ở bốn kích thước. Không có JavaScript page errors trong cả hai bộ. Ảnh đã được xem trực tiếp ở desktop/mobile.

Model/test server: một worker PyTorch CPU, MemoryMax 1600M / SwapMax 128M; mỗi browser chạy tuần tự 512M/64M. Script nhập dữ liệu 400M/32M. Không chạy train, không nạp toàn bộ parquet/SCL vào RAM.

Phép đo riêng với tập 8.192 ứng viên: hồ sơ 1 lần đầu 1,66 giây, cache 0,08 giây; hồ sơ 4 lần đầu 0,84 giây. Peak RSS tiến trình đo 1.212 MiB (có trang mmap dùng chung); không suy ra giới hạn RSS tuyệt đối từ cgroup. Thời gian phụ thuộc cache/hệ thống, không phải cam kết latency production.

Ảnh phiên native tại `/tmp/taobao-preview/`, ảnh so sánh/lịch sử/thay đổi tại `/tmp/taobao-experience-preview/`. Mọi thao tác kiểm thử tạo dữ liệu đều chạy trên bản sao `/tmp/taobao-experience.db` hoặc thư mục tạm của unittest.

## Chỉ số model giữ nguyên ý nghĩa

CSV `/home/midea/Downloads/full_training_metrics.csv` khớp 373 dòng Train trong `full_training.log`: cuối train AUC 0,639602 / GAUC 0,611231 / loss 0,384575. Log gốc dòng 537 báo Eval AUC 0,644728 / GAUC 0,614794 / loss 0,383716. CSV không phải full-test report và Cur_AUC cao nhất 0,706227 chỉ là một batch.

Đánh giá nhỏ hiện có dùng 2.048 impressions, AUC 0,620191 / GAUC 0,592367, vẫn khớp fingerprint inference/checkpoint. Khác tập và cách tính với log gốc; không kết luận model mất chất lượng từ hai con số. Lượt mở rộng demo này chưa đo accuracy/CTR online hoặc A/B; số thay đổi/thẻ trùng trên UI không thay thế các phép đo đó.

## Áp dụng và kiểm tra bản chính

Đã áp dụng vào `data/shopee_muse.db`. Backup ngay trước nhập thêm: `data/backups/before-expand-20261016-012742.db`. Audit `/tmp/taobao-experience-integrity.json` xác minh toàn bộ **8.192** mẫu đầy đủ khớp bốn trường parquet nguồn, toàn bộ hàng cũ của products/muse_item_features không đổi, các bảng người dùng/địa chỉ/hành vi/giỏ/đơn/phiên/voucher/log… giữ nguyên từng hàng. SQLite quick_check và foreign_key_check đều hợp lệ. SHA-256 hai checkpoint vẫn khớp báo cáo trước thay đổi.

Lượt unit cuối `/tmp/taobao-experience-unit-final.log`: **53 PASS**, 18,94 giây. Bổ sung kiểm tra tài khoản mới lấy nhóm từ tương tác web và không gắn nhãn hàng xóm AI khi thiếu vector SCL. Tài khoản mới đã có lượt xem được giải thích theo lịch sử mới hình thành; không tiếp tục gọi là chưa có lịch sử.

Bản chính được khởi động lại qua `shopee-taobao.service`, một worker CPU, giới hạn MemoryMax=1600M / MemorySwapMax=128M. Smoke guest trên port 8000 đã quan sát so sánh hai hồ sơ bằng checkpoint, 12 thẻ và không đổi trạng thái đăng nhập; không tạo hành vi/đơn/tài khoản/log trên database chính. Home và modal phù hợp 320/390/768/1440 px, không có JavaScript page errors. Ảnh `live-*.png` và `live-results.json` ở `/tmp/taobao-experience-preview/`.

Đã dừng server/browser/test riêng, chỉ còn server chính. Lần quan sát cuối MemAvailable khoảng 8 GiB; cgroup server MemoryCurrent khoảng 249 MiB và RSS khoảng 1.258 MiB gồm trang mmap chia sẻ. Không coi các con số này là cam kết tải production hoặc đánh giá online. Không có OOM trong các lượt hoàn tất.
