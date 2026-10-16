# Kiểm tra gợi ý bằng tình huống mua sắm

Tài liệu này mô tả bản catalog `vietnam_tiki_v1` đang chạy. Các phần Taobao native/storefront trong tài liệu cũ là chế độ đối chiếu riêng, không mô tả toàn bộ cách trang chủ hiện tại sắp xếp hàng hóa.

## Vì sao trước đây mua rồi vẫn gặp lại?

Catalog có 2 triệu dòng nhưng nhiều dòng dùng lại cùng mẫu tên, thay màu, shop hoặc thông số sinh tự động. ID khác không đủ chứng minh đây là một mặt hàng khác. Đồng thời, hành vi mua trước đây vẫn tăng ưu tiên ngành hàng mà chưa loại đầy đủ các bản sao của món đã mua. Vì vậy khách có thể gặp lại cùng tai nghe hoặc thêm tai nghe khác ngay sau khi vừa mua.

Quy tắc hiện tại:

- Nhận diện mẫu theo tên đã chuẩn hóa, giữ model và dung lượng thật. Gộp phần thông số mô tả sinh tự động và màu ở sau ` - ` khi chọn gợi ý. iPhone 15 Pro khác iPhone 16 Pro; bản 128 GB khác bản 256 GB. Hai màu của cùng model chỉ chiếm một vị trí gợi ý.
- Đọc đơn của chính tài khoản, bỏ đơn đã hủy, dùng tên snapshot tại lúc đặt nếu có. Không chủ động đề xuất lại các mẫu đã mua trong tối đa 500 dòng sản phẩm mua gần nhất. Đây là giới hạn truy vấn, không phải toàn bộ lịch sử mua không giới hạn.
- Trang chủ mặc định và ưu đãi cá nhân giảm đề xuất loại đồ bền vừa mua trong 30 ngày, ví dụ điện thoại, laptop, tai nghe, giày, sạc và pin dự phòng. Tai nghe nhét tai và chụp tai cùng thuộc khoảng nghỉ này. Nếu vừa mua điện thoại cùng củ sạc, hệ thống cũng tránh mời mua thêm củ sạc khác. Mỹ phẩm/đồ tiêu hao không bị chặn toàn bộ loại theo quy tắc 30 ngày.
- Trong hai ngày đầu sau mua, trang chủ dành tối đa ba vị trí đầu cho phụ kiện bổ trợ còn hợp lệ. Nếu không có phụ kiện phù hợp thì không chèn hàng cho đủ số lượng.
- Chọn ngành hàng trực tiếp vẫn cho xem model khác cùng loại; tìm kiếm và **Mua lại** vẫn giúp tìm lại món đã mua. Bộ lọc sở hữu áp dụng ở các vị trí gợi ý, không xóa hàng khỏi catalog.
- “Sản phẩm tương tự” bắt buộc cùng loại, cùng danh mục, giá từ 0,5 đến 2 lần món đang xem và khác mẫu. “Mua kèm tiện hơn”/giỏ dùng loại bổ trợ, không dùng điện thoại khác để mua kèm điện thoại.
- Loại cáp Lightning với iPhone 15 trở lên; ốp iPhone phải ghi đúng model; sạc cho laptop phải có công suất ghi rõ từ 45 W. Các điều kiện này chỉ loại một số trường hợp sai rõ ràng, chưa chứng nhận đầy đủ cổng cắm, điện áp, công suất thực tế hay kích thước thiết bị.
- Ảnh minh họa chọn theo loại hàng, ổn định cho cùng mẫu; loại chưa có ảnh phù hợp dùng placeholder và không được đưa vào gợi ý. Chi tiết nói rõ ảnh minh họa. Chưa có ảnh xác thực cho từng hãng, model, màu.

Đã loại các ảnh gắn nhãn sai được phát hiện bằng cách xem ảnh trực tiếp: người mẫu thay áo thun, tranh trừu tượng thay robot hút bụi, đồ ăn thay nồi chiên, mỹ phẩm tổng hợp thay đồng hồ, tai nghe có dây thay earbuds. Ảnh chống nắng được thay bằng hình sản phẩm từ trang Anessa chính thức, lưu cục bộ; nguồn ở [sources.json](../static/images/merchandise/sources.json). Với iPhone/Samsung và các hãng có ảnh mẫu sẵn, ưu tiên ảnh cùng hãng thay vì trộn ảnh giữa các hãng. Đây vẫn là ảnh minh họa, chưa xác thực đúng từng model/phiên bản.

Tên chuẩn hóa là heuristic cho catalog demo, chưa thay được SKU/GTIN và bảng biến thể chuẩn từ nhà bán hàng. Không nên coi mọi tên giống nhau trong một catalog thật là cùng một SKU.

## Test case dễ kiểm tra trên giao diện

Các ca tạo/hủy đơn, đổi giỏ phải dùng tài khoản thử hoặc database thử. Không xóa hay thay đơn thật để tái tạo tình huống. Kết quả kỳ vọng là **điều kiện hợp lệ**, không bắt buộc một ID đứng đầu mãi khi lịch sử thay đổi.

| Ca | Input và thao tác | Output kỳ vọng | Dấu hiệu lỗi |
|---|---|---|---|
| 1. Vừa mua tai nghe | Tài khoản có đơn AirPods Pro 2 hoặc Sony WF-1000XM5 chưa hủy; về trang chủ | Không lặp đúng mẫu dưới màu/ID khác; trang chủ mặc định không mời mua thêm tai nghe trong 30 ngày; có thể thấy sạc phù hợp | Vẫn gặp AirPods đổi màu, hoặc cả hàng tai nghe mới ngay sau mua |
| 2. Vừa mua điện thoại | Đặt thử Redmi Note 13 hoặc iPhone; về trang chủ trong hai ngày | Loại mẫu đã mua; ưu tiên tối đa ba phụ kiện hợp lệ, rồi tiếp tục các nhóm sở thích/khám phá | Đưa cùng điện thoại hoặc biến thể màu vào ba vị trí đầu |
| 3. Chủ động xem điện thoại khác | Sau ca 2, chọn tab Điện thoại & Tablet | Có thể có điện thoại model khác; mẫu đã mua vẫn bị loại khỏi gợi ý | Chặn hết điện thoại dù khách chọn xem ngành hàng |
| 4. iPhone 15 Pro | Tìm iPhone 15 Pro, mở chi tiết | Tương tự: điện thoại khác, giá 0,5–2 lần. Mua kèm: sạc, tai nghe, pin/cáp hợp lệ nếu có | Laptop, son, iPhone cùng mẫu đổi màu; cáp Lightning; ốp iPhone 12 hoặc iPhone 15 thường |
| 5. Laptop Dell XPS | Mở chi tiết Dell XPS | Tương tự: laptop khác trong khoảng giá. Mua kèm: bàn phím, chuột, tai nghe, màn hình, sạc đủ điều kiện nếu có | Điện thoại được gọi là laptop; củ sạc 20 W được đề xuất cho laptop |
| 6. Kem chống nắng | Mở Anessa hoặc Perfect UV Milk | Tương tự: chống nắng khác; mua kèm có thể có serum, tẩy trang, dưỡng ẩm | Son/mascara bị gọi là kem chống nắng hoặc serum |
| 7. Giỏ có điện thoại | Thêm điện thoại vào giỏ thử, mở giỏ | Đồ bổ trợ cho ít nhất một món trong giỏ; loại mẫu/biến thể đã có và mẫu đã mua | Thêm một điện thoại khác chỉ vì cùng ngành hàng |
| 8. Đơn hủy | Hủy một đơn thử rồi tải lại gợi ý | Đơn hủy không còn là căn cứ xác định đã sở hữu; món đủ điều kiện được xét lại | Vẫn bị chặn bởi chính đơn đã hủy. Không bắt buộc món phải vào top vì còn điểm/xếp hạng |
| 9. Hai tài khoản | Tài khoản A mua tai nghe; đổi sang B chưa mua | Lịch sử sở hữu của A không chặn hàng cho B | Cả hai cùng bị chặn vì đơn của A |
| 10. Quá khoảng nghỉ | Fixture có đơn điện thoại cách đây 31 ngày | Điện thoại model khác được xét lại; đúng mẫu đã sở hữu vẫn bị loại khỏi gợi ý | Chặn vĩnh viễn toàn bộ loại điện thoại |
| 11. Dung lượng khác | So tên Redmi `(8GB / 128GB)` và `(12GB / 256GB)` | Hai phiên bản vẫn phân biệt; không xóa dung lượng khỏi tên | Gom mọi dung lượng thành một mẫu |
| 12. Hết lựa chọn | Mở loại chỉ còn một mẫu đủ điều kiện | Thông báo chưa có mẫu/phụ kiện phù hợp, không nhét hàng khác loại | Đủ sáu thẻ nhưng sai loại |
| 13. Tìm lại/Mua lại | Tìm theo tên món đã mua hoặc bấm Mua lại ở đơn | Có thể mua lại theo chức năng hiện có | Không tìm được hàng vì bộ lọc gợi ý đã xóa khỏi catalog |
| 14. Lab và giao diện thường | Tắt/bật Chế độ Lab | Bình thường: tên, giá, ảnh, nhãn mua sắm. Lab: ID, P(click)/cosine, trạng thái checkpoint | Điểm kỹ thuật hoặc “độ chính xác” giả xuất hiện trên thẻ mua sắm |
| 15. Tìm kiếm | Nhập từ khóa; bấm ngoài, Esc, chuyển focus | Dropdown đóng; phản hồi chậm không tự mở lại | Dropdown che trang, không đóng được |

## Ví dụ từ checkpoint và catalog đang chạy

Ví dụ cụ thể được ghi đầy đủ trong [merchandise_verification.json](merchandise_verification.json), gồm thời gian, tên, giá, ID dùng đối chiếu và điểm gốc. Đầu vào cố định:

| Món đang xem | Kết quả tương tự quan sát | Kết quả bổ trợ quan sát |
|---|---|---|
| iPhone 15 Pro, ID nội bộ 17438 | iPhone 16 Pro Max | Củ sạc Apple 20 W, tai nghe JBL/Sony |
| Dell XPS, ID nội bộ 20739 | Dell Vostro, MSI Thin GF63, Lenovo Legion | Tai nghe, chuột Logitech, bàn phím Keychron |
| Chống nắng Anessa, ID nội bộ 17150 | Perfect UV Milk | Serum Hyalu B5 |

Không cố định đủ sáu thẻ khi catalog không có sáu mẫu hợp lệ với ảnh riêng. Kết quả mẫu này là khách chưa đăng nhập; khi đăng nhập, MUSE xếp các phụ kiện hợp lệ theo hồ sơ và lịch sử.

## Những đặc trưng nào thực sự được dùng?

Danh sách “40 đặc trưng” không đồng nghĩa checkpoint nhận trực tiếp 40 trường này. Đường suy luận trong [model.py](../app/recommender/model.py) và lớp thương mại trong [service.py](../app/recommender/service.py) có vai trò khác nhau:

| Nhóm bạn nêu | Đường chạy hiện tại | Cách kiểm tra đúng |
|---|---|---|
| Hồ sơ người dùng | MUSE nhận sáu trường ẩn danh `129_1`, `130_1`–`130_5` từ hồ sơ nhập; không có ánh xạ được xác minh rằng `130_2` là hạn mức chi tiêu | Đổi hồ sơ demo và xem raw user/history trong Lab. Đổi tên, số dư, hạng hội viên hoặc năm sinh trên form không chứng minh model đã nhận đặc trưng mới |
| Chuỗi lịch sử | Item `150_2_180`, category `151_2_180`, tối đa 1.000; suy luận giữ phần gần và phần GSU chọn | Kiểm tra lịch sử thật trước/sau thao tác; test tích hợp xác nhận hành vi có thể thay đổi điểm, không yêu cầu mọi thao tác đều đổi top |
| Loại/trọng số hành vi | Mua 5, giỏ 4, thích 3, xem 2 và `0.86^k` là quy tắc lớp xếp feed; `k` là thứ tự sự kiện, không phải số giờ | Dùng test riêng cho quy tắc feed, không gọi đây là trọng số attention học được |
| Thực thể sản phẩm | MUSE dùng ID `205`, nhóm `206`, trường `213`, `214` và SCL 128D qua vocabulary/checkpoint | Kiểm tra ID, maps và điểm giữ nguyên. Tên Việt, giá, tồn kho, sao, giảm giá dùng lọc/hiển thị, không phải đầu vào NLP của checkpoint |
| Cửa hàng/người bán | Shop, Mall, Freeship là nghiệp vụ demo; không có shop encoder riêng trong đường forward hiện tại. Ý nghĩa địa lý cụ thể của `213`/`214` chưa được giải mã/xác minh | Kiểm tra shop/gom vận chuyển bằng test giỏ/báo giá; không tuyên bố những nhãn này đã được model học |
| Ngữ cảnh và suy luận | Home/chi tiết/giỏ quyết định tập ứng viên; cosine/P(click) là kết quả tính toán. Attention là tính toán nội bộ, API không trả `a_i` từng món. Feed kết hợp điểm với các vị trí/ngữ cảnh và loại trùng | Xem `meta.model_used`, `score_type`, `purchase_policy`; điểm click từng ID không bị cộng phần thưởng thương mại |

Kiến trúc tham khảo chính thức: [Alibaba MUSE](https://github.com/alimama-tech/MUSE), [Taobao-MM](https://taobao-mm.github.io/). Metadata tiếng Việt và ảnh minh họa không phục hồi ngữ nghĩa Taobao từ các ID ẩn danh. Thêm nhiều dòng tên/ảnh giả không làm model hiểu hàng hóa tốt hơn.

## Chạy test mà không tràn RAM

Test chính sách dùng SQLite rất nhỏ tự tạo, không sao chép database chính và không nạp model:

```bash
PYTHONPATH=.:tests .venv/bin/python -m unittest test_merchandise test_catalog -v
```

PowerShell trên Windows:

```powershell
$env:PYTHONPATH = ".;tests"
.\.venv\Scripts\python.exe -m unittest test_merchandise test_catalog -v
```

Đối chiếu dữ liệu thật cần đủ checkpoint/maps. Chạy tuần tự khi không có tiến trình kiểm thử model khác; có thể dừng web tạm để chỉ nạp một bản model. Script không tạo tài khoản, giỏ, đơn, hành vi hoặc recommendation logs:

```bash
systemd-run --user --scope -p MemoryMax=1500M -p MemorySwapMax=64M \
  .venv/bin/python -m scripts.verify_merchandise --output docs/merchandise_verification.json
```

Trên Windows, lệnh tương ứng là `.\.venv\Scripts\python.exe -m scripts.verify_merchandise --output docs/merchandise_verification.json`; Windows không có giới hạn systemd, nên đóng các tiến trình model khác trước. Không dùng `unittest discover` trên database chính 4,6 GB vì một số suite cũ sao chép toàn bộ DB. Xem [hướng dẫn Windows](WINDOWS.md).

Các test kiểm chứng quy tắc và lỗi hồi quy. **17/17 điều kiện đạt không phải “gợi ý đúng 100%”.** Muốn có phần trăm phù hợp với người mua phải thu nhãn đánh giá/nhấp/mua trên catalog có metadata xác thực và đo trên tập giữ riêng. P(click) của một món cũng không phải tỷ lệ chính xác toàn hệ thống. Không huấn luyện lại trong lần sửa này.

Kiểm tra giao diện bằng Chromium trên server đang chạy (không tạo đơn/giỏ/hành vi; có đăng nhập demo tạm và log tải gợi ý):

```bash
systemd-run --user --scope -p MemoryMax=1000M -p MemorySwapMax=64M \
  /usr/bin/env PYTHONPATH=. TEST_BASE_URL=http://127.0.0.1:8000 \
  .venv/bin/python tests/browser_merchandise.py
```

Script kiểm tra khách, hai tài khoản đã có đơn, ba trang chi tiết, Lab, khớp thẻ trên giao diện với kết quả API và không tràn ngang ở 390/1440 px. Ảnh chụp viewport lưu tại `/tmp/lumi-merchandise-preview`; không chụp toàn trang dài hoặc sao chép database lớn.

## Kết quả lượt kiểm tra bản sửa

| Phạm vi | Kết quả | Đỉnh RAM cgroup quan sát |
|---|---|---|
| Chính sách hàng hóa + catalog + bốn ca tích hợp checkpoint/fallback/đánh giá/tìm kiếm | 24 test đạt | 224,4 MB |
| Đối chiếu catalog/checkpoint thật, hai tài khoản và ba sản phẩm | 17 điều kiện đạt, không đổi số dòng đơn/giỏ/tài khoản/hành vi/log | 213,1 MB |
| Chromium: khách, hai tài khoản, desktop/mobile, Lab, chi tiết, lỗi 503 và thử lại | 7 nhóm luồng đạt, không page error hay tràn ngang ở viewport đã thử | 325,6 MB |

Các lượt này chạy tuần tự, swap quan sát bằng 0. Giới hạn test model 1.400–1.500 MB, Chromium 1.000 MB. Server đang chạy một worker trong `lumi-commerce.service`, `MemoryMax=1800M`, `MemorySwapMax=128M`. Đây là kiểm thử chức năng có giới hạn, chưa phải thử tải nhiều khách đồng thời hoặc đo tỷ lệ gợi ý phù hợp với người mua.
