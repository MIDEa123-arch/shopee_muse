> **Cập nhật gợi ý theo loại hàng — 16/10/2026:** giao diện hiện có bộ lọc ngữ cảnh, lọc thẻ trùng và ẩn mã sản phẩm khỏi màn mua sắm. Điểm MUSE giữ nguyên nhưng tập kết quả hiển thị đã thay đổi. Xem [CONTEXT_RECOMMENDATIONS.md](CONTEXT_RECOMMENDATIONS.md) cho quy tắc và kiểm thử mới. Nội dung bên dưới lưu mốc commerce trước lớp lọc này.

> **Giao diện hiện tại — Lumi commerce, 16/10/2026:** ảnh/tên tiếng Việt được gắn qua bảng hiển thị riêng; giữ nguyên điểm và thứ tự model. Xem [STOREFRONT.md](STOREFRONT.md) cho luồng commerce, giới hạn ngữ nghĩa, kiểm chứng và cách chạy. Các mô tả giao diện mã/hình học bên dưới là lịch sử trước commerce.

> **Lượt cải thiện demo tiếp theo — 16/10/2026:** 53 kiểm thử Python và hai bộ Chromium native/experience đã qua trên bản sao dữ liệu. Bổ sung 5.989 ID thật, tổng 8.192 ứng viên / 1.269 nhóm; so sánh hai hồ sơ chỉ đọc, thống kê nhóm từ lịch sử gốc, so sánh trước/sau thực và xử lý lỗi tải lại có retry. Chi tiết trong [DEMO_EXPERIENCE.md](DEMO_EXPERIENCE.md). Các mốc 50 test và 2.203 ứng viên bên dưới là kết quả của lần chuyển đổi trước.

# Kết quả kiểm chứng — 16/10/2026

**50 kiểm thử Python: PASS. Bộ Chromium native: PASS (13 nhóm luồng, đủ 8 hồ sơ, 4 kích thước màn hình).** Thử tạo tài khoản/đặt/hủy đơn dùng SQLite bản sao, không dùng dữ liệu chính. Bản danh mục mới đã được áp dụng vào `data/shopee_muse.db` sau sao lưu.

## Tính toàn vẹn

Đối chiếu trước/sau với `data/backups/20261016-002445/before-taobao.db`:

| Dữ liệu được giữ nguyên từng hàng | Số lượng |
|---|---:|
| Người dùng | 14 |
| Địa chỉ | 8 |
| Đơn / chi tiết đơn | 1 / 1 |
| Dòng giỏ | 2 |
| Đặc trưng sản phẩm / hồ sơ | 5.622 / 8 |
| imported_click | 8.000 |
| click / favorite / add_to_cart / purchase thật | 45 / 1 / 3 / 1 |

ID nội bộ và raw ID toàn bộ 5.622 sản phẩm giữ nguyên. Hai checkpoint được tính lại SHA-256 theo chunk 1 MiB, khớp hoàn toàn báo cáo offline trước thay đổi:

- dense: `ac3b7fce48232977f072c81d6056fc0cdd381de9582a88fa417bb4217e30844b`
- sparse: `5add00cb287d635418dbfcad74f778565dd58224aa8fe585a3531abb589309bd`

Migration đối chiếu 2.203 sản phẩm đủ cả bốn trường 205/206/213/214 với parquet gốc; xác minh cả tám hồ sơ (đặc trưng và cặp chuỗi ID/nhóm) với test-shard gốc. 3.419 mẫu lịch sử thiếu item features đầy đủ không được đưa vào danh sách mới. Có 941 nhóm có ứng viên đầy đủ. `quick_check=ok`, `foreign_key_check=[]` sau khi dọn ba hàng mồ côi có sẵn trước chuyển đổi (một session, một recommendation log, một thông báo tham chiếu user đã không tồn tại; bản gốc nằm trong backup).

## Kiểm thử tự động

50 test Python gồm 41 hợp đồng thương mại/nhánh danh mục cũ và 9 test native/tính toàn vẹn. Các test cũ lấy fixture trước chuyển đổi qua đường backup được ghi trong database; test native dùng bản sao danh mục gốc. Lượt cuối chạy toàn bộ bằng database chính làm nguồn chỉ đọc, hoàn tất trong 10,04 giây.

- Full ranking trên cả 8 hồ sơ, 2.203 ứng viên đầy đủ, điểm giảm dần và so trực tiếp output checkpoint. Prefix 24/60 ổn định, cache đúng khóa và bị thay sau hành vi thật.
- Lọc nhóm không ghi click giả; API demo-interest bị từ chối trong native mode. Giữ chuỗi raw gốc, ID int64 truyền dưới dạng chuỗi.
- Tìm kiếm nhóm/mã, AI search toàn danh mục, pagination qua trang 6; SCL cosine, loại mục tiêu và món đã có trong giỏ.
- Cold start không mượn ID người dùng mẫu; model lỗi có fallback, bỏ điểm và nhãn AI.
- Giữ kiểm thử session, phân quyền, validation, địa chỉ mặc định, giỏ/chọn hàng, báo giá thay đổi giữa tab, chống trùng đơn, tranh món cuối, rollback, voucher/hoàn tiền đúng một lần, mua ngay/mua lại/đánh giá.
- Dọn hàng session/log/notice mồ côi giữ nguyên hàng của user hợp lệ, chạy lặp an toàn.

Chromium native xác minh guest, đủ 8 hồ sơ, xem thêm, lọc không tạo hành vi giả, giải thích chất lượng, Lab, chi tiết/SCL, lưu yêu thích, thêm giỏ, tìm kiếm/phân trang, thêm nhanh, chọn tất cả, thanh toán, đặt/hủy đơn, hồ sơ/địa chỉ, cold start và fallback. Giả lập HTTP 503 ở gợi ý giỏ/đơn/thành công: giữ nội dung nghiệp vụ và nút điều hướng sau đặt đơn hoạt động ngay. Không có JavaScript page errors. Không phát hiện chữ Trung trên các màn hình kiểm tra.

Home, feed, chi tiết, danh mục, giỏ và checkout đều kiểm tra tràn ngang tại **320/390/768/1440 px**. Chụp viewport, đã xem trực tiếp ảnh desktop/mobile và tăng chữ phần AI cho dễ đọc. Thông số MUSE/P(click)/GAUC chỉ hiện trong Lab; không có % phù hợp nội suy trên thẻ.

`git diff --check`, `bash -n start_server.sh`, Python compile: PASS. Mã JavaScript đã được Chromium thực thi qua toàn bộ luồng nêu trên; môi trường không có Node.

## Chất lượng checkpoint

Báo cáo [recommendation_evaluation.json](recommendation_evaluation.json) vẫn khớp fingerprint checkpoint/maps/mã suy luận, được kiểm tra lại khi chuyển đổi. Không huấn luyện hoặc thay checkpoint, không tuyên bố AUC tăng nhờ sửa UI.

| Chỉ số trên mẫu thử 2.048 impressions / 207 users / 4 shards | Kết quả |
|---|---:|
| AUC / GAUC | 0,620191 / 0,592367 |
| Log loss / baseline CTR cố định | 0,403770 / 0,414837 |
| Accuracy tại 0,5 / luôn đoán không click | 85,45% / 85,45% |
| Precision / Recall tại 0,5 | 0% / 0% |
| P@10 / baseline ngẫu nhiên cùng nhóm | 17,73% / 14,73% |
| P@10 lift | 1,203× |

Chất lượng xếp hạng có tín hiệu, chưa mạnh. Toàn bộ dự đoán trong mẫu nằm dưới ngưỡng 0,5; accuracy không có giá trị chứng minh tốt hơn baseline. GAUC gồm 119 user có đủ hai nhãn, P@10 gồm 22 user có ít nhất 20 ứng viên và đủ hai nhãn. 62,02% trên giao diện là AUC × 100 với cặp bằng điểm tính nửa, không phải % phù hợp của sản phẩm hoặc độ chính xác toàn tập. Chưa có đánh giá online/A-B hoặc nhãn tương đồng hàng hóa để đánh giá SCL neighbours.

## RAM và bằng chứng chạy

Tất cả lượt test model/server dùng `.venv` PyTorch CPU, một worker, không reload, `MemoryMax=1600M` / `MemorySwapMax=128M`. Browser chạy riêng `512M/64M`, mỗi lần một Chromium. Migration đọc batch 32.768 item rows và 16 user rows, giới hạn `400M/32M`. Không nạp toàn bộ embedding, parquet hoặc train lại.

Đo full catalog: hồ sơ 1 lần đầu 4,45 giây, lần cache 0,02 giây; hồ sơ 2 lần đầu 2,11 giây. Peak RSS tiến trình đo 617 MiB. MemAvailable các lần kiểm tra cuối khoảng 8–9 GiB. RSS của mmap có thể gồm trang chia sẻ; không diễn giải cgroup limit thành cam kết RSS tuyệt đối. Không có OOM trong các lượt native hoàn tất.

- Log unit cuối: `/tmp/taobao-all-tests-final.log`.
- Log Chromium cuối: `/tmp/taobao-browser-final.log`.
- Toàn vẹn/hash: `/tmp/taobao-integrity.json`.
- Ảnh và kết quả browser: `/tmp/taobao-preview/`, `browser-results.json`.
- Backup ngay trước transaction: `data/backups/before-native-20261016-004231.db`.

Không coi các test này là bảo đảm không còn lỗi trong mọi tình huống. Chưa kiểm chứng tải production, thanh toán/OTP/giao nhận thật hoặc đánh giá toàn test set; mua hàng trên bản này vẫn là mô phỏng.

## Bản đang chạy

Web chính hoạt động tại `http://localhost:8000` qua user service `shopee-taobao.service`, PyTorch CPU một worker, không reload, MemoryMax 1600M/SwapMax 128M. Health trả `model_ready=true`; catalog trả native mode, 2.203 ứng viên và tám hồ sơ đã xác minh. Đã smoke trực tiếp bằng guest trên bản chính (home, tìm Nhóm 001, SCL chi tiết, 320/390/768/1440 px), không tạo đơn/tài khoản hoặc hành vi thử trên dữ liệu chính; không có lỗi JavaScript. Ảnh `live-*.png` nằm trong `/tmp/taobao-preview/`.

Các tiến trình server/browser/unit test riêng đã dừng; chỉ còn một server ứng dụng trên cổng 8000. Service báo MemoryCurrent khoảng 209 MiB, RSS tiến trình khoảng 725 MiB gồm trang mmap dùng chung; MemAvailable khoảng 8,4 GiB. Quản lý bằng `systemctl --user status|restart|stop shopee-taobao.service`; xem log bằng `journalctl --user -u shopee-taobao.service`. `./start_server.sh` nhận ra server đã hoạt động và không nạp thêm model.
