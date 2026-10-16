> **Giao diện hiện tại — Lumi commerce, 16/10/2026:** ảnh/tên tiếng Việt được gắn qua bảng hiển thị riêng; giữ nguyên điểm và thứ tự model. Xem [STOREFRONT.md](STOREFRONT.md) cho luồng commerce, giới hạn ngữ nghĩa, kiểm chứng và cách chạy. Các mô tả giao diện mã/hình học bên dưới là lịch sử trước commerce.

> **Cập nhật trải nghiệm mở rộng — 16/10/2026:** danh mục hiện tại có 8.192 ứng viên thật / 1.269 nhóm. Xem [DEMO_EXPERIENCE.md](DEMO_EXPERIENCE.md) cho bổ sung dữ liệu, hồ sơ, so sánh và kiểm thử mới nhất. Các số 2.203/941 bên dưới mô tả mốc chuyển đổi ban đầu.

# Chuyển sang dữ liệu Taobao gốc — 16/10/2026

Mục tiêu là phục vụ đúng checkpoint sẵn có, không huấn luyện hoặc sửa vocabulary. Mô hình không học quan hệ với ảnh, tên thương hiệu và ngành hàng tiếng Việt đã được ghép vào các raw ID ở bản cũ. Bản mới bỏ lớp ghép này khỏi trải nghiệm khám phá.

## Dữ liệu và tính toàn vẹn

`migrate_taobao.py` đọc bốn cột `205/206/213/214` trong `raw/item_features.parquet`, mỗi batch 32.768 dòng. Mọi mẫu đầy đủ đều được đối chiếu chính xác cả bốn trường với `muse_item_features`. Trường 205 là ID sản phẩm, 206 là nhóm, **213 là thành phố và 214 là tỉnh**, không phải shop/brand. Cả tám hồ sơ và cặp chuỗi lịch sử cũng được đối chiếu với shard gốc theo batch 16 dòng. Các trường địa lý là ID ẩn danh, không được tự đổi thành tên địa phương.

- 5.622 ID hiện có được giữ nguyên, không xóa lịch sử, người dùng, địa chỉ, giỏ hoặc snapshot đơn.
- 2.203 ID khớp item-feature gốc đầy đủ, được dùng làm ứng viên mới.
- 3.419 ID vắng trong bảng item-feature công khai được đối chiếu cặp ID/nhóm với chuỗi người dùng gốc. Giữ để đọc lịch sử, đánh dấu thiếu đặc trưng và không bán/gợi ý mới. Không coi giá trị địa lý 0 mặc định là metadata đã xác minh.
- Ánh xạ 1:1 raw nhóm → alias `Nhóm NNN`; 941 nhóm có ứng viên đầy đủ. Các alias không khẳng định loại hàng.
- Tên `Mẫu TB-NNNNN` dựa trên ID nội bộ ổn định. Hình SVG do mã vẽ theo hash ID, không mô tả nội dung hàng hóa, không giải mã vector SCL.
- `catalog_settings` ghi chế độ, số lượng và đường dẫn backup. `products` ghi nguồn, mức đầy đủ và raw nhóm/địa lý dưới dạng TEXT để không mất số nguyên 64-bit khi đi qua JavaScript.
- Hai checkpoint, các `.npy`, `muse_item_features` và `muse_user_features` giữ nguyên. Chỉ xóa tín hiệu `demo_interest` từng được tạo giả để ưu tiên ngành hàng; không xóa click/favorite/add_to_cart/purchase thật.

Tên và ảnh gốc không thể lấy từ các parquet đang có: đây là giới hạn của [Taobao-MM công khai](https://taobao-mm.github.io/), không phải lỗi tải ảnh. Các file raw, checkpoint và backup không đưa lên Git.

## Xếp hạng

`native.py` chấm toàn bộ 2.203 mẫu đầy đủ bằng cùng `MuseModel.predict` và checkpoint hiện có. Mỗi lần dự đoán theo lô 64, torch CPU hai luồng; mmap dùng MADV_RANDOM tránh readahead lớn. Không lấy prefix theo lượng bán giả, không chỉ chọn 128 ID bằng SCL trước khi chấm, không đổi thứ hạng bằng điểm cộng sở thích demo hoặc giãn ngành hàng.

Khóa cache gồm database, model, user, tập ứng viên và 1.000 hành vi thật gần nhất. Cache tối đa tám khóa, TTL 300 giây. Lock dùng chung cho suy luận full catalog và cosine để tránh nạp/chạy nhiều lượt nặng song song. Kết quả cùng điểm dùng ID nội bộ tăng dần làm khóa phụ. Pagination, tìm kiếm AI và lọc nhóm dùng cùng thứ hạng, có kiểm thử so trực tiếp điểm output với checkpoint.

Nhóm chỉ là bộ lọc, không thay lịch sử. Native API từ chối POST demo-interest để không đưa click giả vào model. Gợi ý tương tự dùng SCL cosine trên các mẫu đầy đủ; không có nhãn thật để kết luận độ đúng về loại/ảnh sản phẩm. Gợi ý tại giỏ và đơn là khám phá tiếp theo lịch sử, không tuyên bố đã học đồng mua.

## Giao diện

Trang khám phá, nhóm, tìm kiếm và chi tiết được thiết kế lại bằng tiếng Việt. Thẻ chỉ hiện mã, nhóm, hình nhận diện và nhãn AI khi thực sự dùng model. Không có rating, lượng bán, thương hiệu, giảm giá hoặc phần trăm phù hợp giả. Có giải thích ảnh ẩn danh ở trang chủ/chi tiết. Mua thử thu gọn trong chi tiết; giá, ví và giao nhận mô phỏng được ghi rõ.

MUSE và thông số kỹ thuật chỉ trong Lab. Khách chưa đăng nhập không được gắn nhãn AI cá nhân hóa. Tài khoản mới dùng cold start. Khi suy luận lỗi, bỏ điểm/nhãn AI và trả danh mục thứ tự ID rõ ràng.

Báo cáo offline hiện có khớp fingerprint: AUC 0,620191, GAUC 0,592367, log loss 0,403770 so baseline 0,414837. Đây là mẫu thử 2.048 lượt hiển thị, không phải toàn tập. Chất lượng có ích nhưng còn hạn chế; đổi giao diện/danh mục không được dùng làm bằng chứng AUC tăng. Accuracy @0,5 bằng luôn đoán không click nên không quảng bá con số đó.

## Vận hành và hoàn tác

Backup trước thay đổi lớn: `data/backups/20261016-002445/before-taobao.db`. Script migration tạo thêm bản sao trước transaction và ghi đường dẫn vào `catalog_settings.migration_backup`. Đơn cũ giữ snapshot cũ để bảo toàn nghiệp vụ. Đã dọn ba hàng mồ côi có sẵn (session, log gợi ý, thông báo tham chiếu người dùng không tồn tại); không thay dữ liệu của người dùng hợp lệ, bản gốc giữ trong backup.

Muốn hoàn tác dữ liệu: dừng server, sao lưu trạng thái hiện tại trước, dùng SQLite backup API từ bản trước chuyển đổi vào database mới rồi chạy với `DATABASE_PATH` trỏ tới bản đó. Không ghi đè database đang mở; việc phục hồi backup cũ sẽ không chứa những giao dịch mới phát sinh sau chuyển đổi.

Lượt đo thử full catalog: hồ sơ 1 lần đầu 4,45 giây, cache 0,02 giây; hồ sơ 2 lần đầu 2,11 giây. Đỉnh RSS tiến trình đo 617 MiB, chạy trong scope MemoryMax 1600M/SwapMax 128M. Đây là phép đo cục bộ, không phải bảo đảm tải đồng thời. Bộ test trình duyệt chạy riêng giới hạn 512M/64M, chụp viewport để tránh ảnh toàn trang quá dài.

Bản chính đang dùng `shopee-taobao.service` (user systemd), port 8000, CPU/một worker và giới hạn 1600M/128M. Đây là service tạm của phiên hiện tại; sau khi khởi động lại máy có thể dùng `./start_server.sh`. Các tiến trình test được dừng sau kiểm chứng. Xem [VERIFICATION.md](VERIFICATION.md) cho số liệu và ảnh bản đang chạy.
