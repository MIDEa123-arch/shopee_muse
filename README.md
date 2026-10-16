# Lumi · Cửa hàng trải nghiệm

**Chạy trên Windows:** xem [hướng dẫn Windows từng bước](docs/WINDOWS.md). Sau khi cài thư viện và copy database/model theo hướng dẫn, mở PowerShell tại thư mục repo rồi chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_windows.ps1
```

Mở http://localhost:8000. Git không chứa database, checkpoint và các file `.npy` nhiều GB; các file này cần được chuyển riêng từ máy đang chạy. Script dùng một worker CPU, kiểm tra đủ file trước khi khởi động. Chưa kiểm thử thực thi trên Windows thật.

**Trạng thái catalog hiện tại:** database chính dùng `vietnam_tiki_v1` với 2 triệu dòng; phần bên dưới mô tả thêm chế độ Taobao native/storefront đã xây dựng để đối chiếu model. Quy tắc mới và giới hạn dữ liệu nằm trong [CONTEXT_RECOMMENDATIONS.md](docs/CONTEXT_RECOMMENDATIONS.md). Thuật ngữ kỹ thuật chỉ hiện trong Lab; gợi ý tìm kiếm đóng khi bấm ra ngoài, nhấn Esc hoặc chuyển Tab ra khỏi vùng tìm kiếm.

**Bản sửa gợi ý sau mua:** loại mẫu đã mua kể cả khác ID/màu, bỏ đơn hủy, nghỉ gợi ý cùng loại đồ bền 30 ngày ở trang chủ mặc định, ưu tiên phụ kiện trong hai ngày đầu. Chi tiết/giỏ kiểm tra loại hàng và một số điều kiện tương thích trước khi xếp điểm; giữ model/dung lượng khi gộp mẫu. Xem [test case có input/output, ví dụ thật và giải thích các đặc trưng](docs/TEST_CASE_GOI_Y.md), [báo cáo kiểm tra dữ liệu thật](docs/merchandise_verification.json). Đây là quy tắc cho catalog hiện tại, không phải phép đo tăng độ chính xác của checkpoint.

Web tiếng Việt sử dụng checkpoint MUSE đã huấn luyện trên **Taobao-MM**, không huấn luyện lại. FastAPI, SQLite và HTML/CSS/JavaScript thuần; không cần Node để chạy.

Danh mục hiện có **8.192 mẫu với đặc trưng sản phẩm gốc** thuộc **1.269 nhóm**. Bổ sung 5.989 ID thật từ parquet Taobao, giữ nguyên 5.622 ID ban đầu, tổng 11.611 ID. Trong đó 3.419 ID chỉ có trong chuỗi lịch sử, thiếu đặc trưng sản phẩm đầy đủ nên không được dùng làm ứng viên mới. Giữ nguyên ID 64-bit, ánh xạ vocabulary, đặc trưng và lịch sử của 8 hồ sơ gốc.

Taobao-MM không công bố tên hoặc ảnh gốc. Giao diện commerce mới dùng **157 cặp tên/ảnh mẫu từ DummyJSON**, Việt hóa tên, chia thành 8 ngành hàng minh họa. Ảnh được lưu cục bộ, tổng khoảng 1,3 MB. Danh mục hiển thị nằm riêng trong `product_presentations`, giữ nguyên bảng sản phẩm, ID, nhóm, đặc trưng, lịch sử và trọng số model. **Đây không phải metadata Taobao gốc, không xác nhận độ phù hợp ngữ nghĩa của gợi ý với hàng hóa trong ảnh.** Web lọc theo loại hàng đang quan tâm, giữ một thẻ cho mỗi cặp tên/ảnh và ẩn mã kỹ thuật khỏi màn mua sắm. Điểm từng ID giữ nguyên, danh sách hiển thị thay đổi theo bộ lọc. Xem [quy tắc gợi ý hiện tại](docs/CONTEXT_RECOMMENDATIONS.md). [Dữ liệu Taobao](https://taobao-mm.github.io/) · [Nguồn ảnh/tên mẫu](https://dummyjson.com/docs/products).

## Chạy

```bash
cd /home/midea/Projects/shopee_muse
./start_server.sh
```

Mở http://localhost:8000. Script ưu tiên `.venv` có PyTorch CPU, chạy một worker, không bật reload để tránh nạp nhiều bản model. Có thể cấu hình `HOST`, `PORT`, `PYTHON_BIN`.

Các đường dẫn mặc định:

- Database: `data/shopee_muse.db` (`DATABASE_PATH`).
- Dữ liệu: `data/` (`MUSE_DATASET_DIR`), thư mục này cần chứa `feature_map/`. Có thể trỏ tới thư mục dataset bên ngoài bằng biến môi trường.
- Checkpoint: `checkpoints/` (`MUSE_CHECKPOINT_DIR`).
- Demo: `DEMO_MODE=true`; có 8 hồ sơ mẫu và Lab. Tài khoản mới dùng cold start, không mượn raw user ID.

Chuyển một database cũ sang danh mục gốc:

```bash
systemd-run --user --scope -p MemoryMax=400M -p MemorySwapMax=32M \
  .venv/bin/python -m scripts.migrate_taobao
```

Script tự sao lưu SQLite trước transaction, xác minh từng ID với `raw/item_features.parquet`, giữ dữ liệu người dùng/đơn/giỏ và checkpoint. Chạy lại an toàn. Không chạy các script tạo lại bảng sản phẩm cũ trên database đã chuyển đổi. Đơn cũ giữ nguyên snapshot tại thời điểm đặt.

Mở rộng ứng viên theo các nhóm gốc:

```bash
systemd-run --user --scope -p MemoryMax=400M -p MemorySwapMax=32M \
  .venv/bin/python -m scripts.expand_taobao_catalog
```

Script dùng chọn mẫu xác định theo ID, lấp nhóm thưa trước; chỉ nhập ID có cả embedding checkpoint và vector SCL. Giữ nguyên dữ liệu cũ, tự backup và chạy lặp an toàn. Sau nhập thêm dữ liệu, khởi động lại server để nạp tập đặc trưng mới.

Gắn giao diện commerce sau khi đã chuyển đổi/mở rộng dữ liệu:

```bash
uv pip install --python .venv/bin/python -r requirements-dev.txt
systemd-run --user --scope -p MemoryMax=400M -p MemorySwapMax=32M \
  .venv/bin/python -m scripts.build_storefront
```

Khởi động lại server sau khi gắn metadata. Script tự backup, chỉ ghi bảng hiển thị và cấu hình nguồn. Không nạp model; tối đa hai ảnh tải đồng thời khi ảnh chưa có. Bản snapshot nguồn tại `app/storefront_source.json`, manifest ảnh tại `static/images/storefront/sources.json`. Nếu chưa gắn metadata, giao diện nhận diện ID cũ vẫn hoạt động.

## Gợi ý hoạt động thế nào?

- Chấm toàn bộ ứng viên có đặc trưng đầy đủ bằng checkpoint, lô 64 trên CPU; sắp xếp P(click) giảm dần. Không cộng điểm ngành hàng/giá/ảnh minh họa, không ép kết quả bằng `demo_interest`.
- Trang chủ dành chỗ cho mẫu chưa xem, loại ID có trong lịch sử gốc và 1.000 hành vi thật gần nhất. Tìm kiếm vẫn cho phép tìm lại mọi mẫu.
- Lưu đệm tối đa 8 phiên lịch sử trong 5 phút; hành vi xem, lưu, thêm giỏ hoặc mua làm thay đổi khóa lịch sử. Một khóa suy luận tránh chấm trùng khi có nhiều yêu cầu cùng lúc.
- Tìm kiếm theo tên tiếng Việt, lọc ngành hàng minh họa và giá dùng lớp hiển thị riêng. Trang chủ theo loại hàng vừa xem/lưu/thêm giỏ; chi tiết, giỏ và sau mua có bộ lọc cùng loại. Một ảnh/tên hiện một lần. Khi hết lựa chọn cùng loại, có nút trở lại toàn bộ thay vì lấp hàng khác loại. Khi chọn AI gợi ý, kết quả giữ thứ tự điểm checkpoint trong tập đã lọc. Lọc không tạo click giả hay cộng điểm. Xem thêm giữ nguyên thứ tự khi lịch sử chưa đổi.
- Trang chi tiết tìm hàng xóm bằng cosine của vector SCL gốc; không tuyên bố tương đồng về ảnh hoặc loại hàng. Giỏ loại trừ các mẫu đã có; đơn mua thử có thể tiếp tục khám phá.
- Khi model lỗi, danh mục theo ID vẫn hoạt động, bỏ nhãn AI và phần trăm đánh giá. Khách chưa đăng nhập xem danh mục gốc, không tự đăng nhập.
- MUSE, raw ID, P(click), cosine và các thông số chỉ hiện trong **Chế độ Lab**. Giao diện mua sắm dùng các nhãn thông thường như “Sản phẩm tương tự” và “Mua kèm tiện hơn”.

## Trải nghiệm mua sắm và cá nhân hóa

- Trang chủ có banner, ảnh ngành hàng, danh sách AI và thêm giỏ nhanh. Chi tiết có giá, số lượng, mua ngay, yêu thích, mô tả/nguồn, đánh giá và gợi ý SCL. Tên, ảnh và giá thống nhất qua giỏ, báo giá và snapshot đơn hàng.
- Hồ sơ hiện gọn trên trang chủ; hoạt động gần đây có thể mở xem. Gợi ý SCL ở chi tiết tách khỏi xếp hạng checkpoint chính. Thông số MUSE chỉ trong Lab.
- Sau tương tác, so sánh 12 gợi ý đầu trước/sau: số mẫu mới và đổi vị trí tính từ kết quả thực. Phân biệt tác động của lịch sử và việc bỏ qua mẫu đã xem; không coi thay đổi danh sách là độ chính xác hoặc huấn luyện lại.
- So sánh hai hồ sơ mẫu trên cùng tập ứng viên, hiển thị số mẫu trùng. API chỉ đọc, không đổi phiên đăng nhập, không tạo lịch sử hoặc recommendation logs; bị chặn khi tắt demo.
- Lỗi tải lại giữ danh sách trước, có trạng thái và nút thử lại. Guard theo người dùng/route/request ngăn dữ liệu trả chậm ghi nhầm màn hình.

## Chất lượng và giới hạn

Báo cáo [recommendation_evaluation.json](docs/recommendation_evaluation.json) lấy mẫu 2.048 lượt hiển thị thử nghiệm gốc, 207 user, 4 shards. AUC **0,620191**, GAUC **0,592367**; P@10 cao hơn chọn ngẫu nhiên khoảng **1,20 lần** trên các user đủ điều kiện. Khả năng xếp hạng có tín hiệu, chưa mạnh. Accuracy 85,45% tại ngưỡng 0,5 bằng baseline luôn đoán không click, không được dùng để quảng bá độ chính xác.

**62,02%** trong báo cáo Lab là tỷ lệ xếp đúng cặp nhấp/không nhấp (AUC, tính nửa điểm cho cặp bằng nhau), không phải tỷ lệ sản phẩm phù hợp hay xác suất mua. Thay danh mục không tự làm tăng AUC checkpoint. Báo cáo chỉ hiện khi fingerprint checkpoint/maps/mã suy luận khớp.

Ảnh, tên hàng, giá và shop Taobao thật không có trong bộ công khai. Giá hiển thị là giá mô phỏng, quy đổi cố định từ giá mẫu DummyJSON, không phải báo giá thị trường. Kho, ví, voucher, địa chỉ, giao nhận và mua hàng là **mô phỏng**. Tài khoản, lượt xem, lưu yêu thích và đơn thử vẫn được lưu thật trong SQLite. Không liên kết với Taobao, Shopee hay các thương hiệu trong ảnh.

## Kiểm thử tiết kiệm RAM

Chạy tuần tự, không huấn luyện và không nạp cả parquet/embedding vào RAM:

Các test native/storefront sao chép database đầu vào. Với database 2 triệu dòng hiện tại, cần trỏ `DATABASE_PATH` tới **fixture Taobao nhỏ riêng** trước khi chạy các test này; không chạy toàn bộ suite trực tiếp trên database 4,6 GB. Lệnh đầy đủ bên dưới chỉ phù hợp khi database đầu vào là fixture nhỏ.

```bash
systemd-run --user --scope -p MemoryMax=1600M -p MemorySwapMax=128M \
  .venv/bin/python -m unittest discover -s tests -v
```

Bộ test tự dùng bản sao database. Các kiểm thử hợp đồng thương mại/danh mục cũ dùng bản sao lưu trước chuyển đổi; `test_native.py` kiểm thử nguồn/suy luận; `test_storefront.py` kiểm tra **65.536 điểm dự đoán giữ nguyên tuyệt đối** khi bật/tắt metadata hiển thị, thứ tự 60 gợi ý đầu của 8 hồ sơ và tính nhất quán giỏ/báo giá/đơn.

Để kiểm thử trình duyệt, tạo bản sao SQLite riêng bằng SQLite backup API, chạy server trên port 8011 với `DATABASE_PATH` trỏ tới bản sao, rồi:

```bash
systemd-run --user --scope -p MemoryMax=512M -p MemorySwapMax=64M \
  .venv/bin/python tests/browser_storefront.py

systemd-run --user --scope -p MemoryMax=512M -p MemorySwapMax=64M \
  .venv/bin/python tests/browser_context.py
```

Bộ test trình duyệt tạo đơn, tài khoản và hành vi thử: **chỉ chạy trên database riêng**. `TEST_BASE_URL`, `TEST_SCREENSHOT_DIR` cấu hình URL/ảnh. Chụp viewport thay vì ảnh toàn trang dài để tránh tăng RAM. `browser_native.py`/`browser_experience.py` giữ kịch bản giao diện mã/hình học trước commerce; các script browser cũ khác lưu kịch bản danh mục cũ.

Kiểm thử riêng việc đóng/mở gợi ý tìm kiếm (chỉ đọc server, giả lập API gợi ý để kiểm tra cả phản hồi chậm):

```bash
TEST_BASE_URL=http://127.0.0.1:8000 .venv/bin/python tests/browser_search.py
```

[Gợi ý theo loại hàng hiện tại](docs/CONTEXT_RECOMMENDATIONS.md) · [Giao diện commerce](docs/STOREFRONT.md) · [Lịch sử mở rộng dữ liệu](docs/DEMO_EXPERIENCE.md) · [Chi tiết chuyển đổi](docs/TAOBAO_NATIVE.md) · [Báo cáo kiểm chứng](docs/VERIFICATION.md)
