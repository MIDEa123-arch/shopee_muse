# Gợi ý commerce theo loại hàng — 16/10/2026

## Trạng thái đang chạy

Cập nhật chính sách mua hàng và ảnh: xem [test case hiện tại](TEST_CASE_GOI_Y.md) và [đối chiếu dữ liệu thật](merchandise_verification.json). Catalog tiếng Việt hiện loại mẫu đã mua/biến thể màu, bỏ đơn hủy, áp dụng khoảng nghỉ đồ bền trên trang chủ và kiểm tra loại phụ kiện cụ thể. Các kết quả test và service name ở phần lịch sử phía dưới mô tả những lần triển khai trước.

Service chính hiện dùng catalog `vietnam_tiki_v1` gồm 2.000.000 dòng sản phẩm. Giao diện khách hàng chỉ dùng ngôn ngữ mua sắm thông thường; tên MUSE, raw ID, P(click), cosine và thông số mô hình chỉ xuất hiện sau khi bật **Chế độ Lab**. Tên hiển thị đã bỏ phần thông số ghép trong ngoặc, mã sản phẩm không hiện ở thẻ hoặc chi tiết, và ảnh/tên trùng không được dùng để lấp đủ số lượng.

Các vị trí có mục đích riêng:

- Trang chủ dùng hành vi xem, yêu thích, giỏ và mua gần đây để điều chỉnh thứ tự, sau đó giãn danh mục và bỏ ảnh/tên trùng.
- Tìm kiếm bắt buộc khớp từ hoặc cụm từ trước khi model xếp lại các kết quả hợp lệ. Ví dụ “nước hoa” không còn khớp sai với “khoáng”; “kem chống nắng” chỉ trả đúng cụm hàng này khi catalog có kết quả.
- Chi tiết “Sản phẩm tương tự” giữ cùng loại, cùng danh mục và khoảng giá 0,5–2 lần; độ tương đồng chỉ xếp hạng bên trong tập đó.
- “Mua kèm tiện hơn” và giỏ hàng dùng danh sách ngành hàng bổ trợ. Điện thoại chỉ ghép tai nghe, sạc, cáp, pin, ốp hoặc bao da; laptop chỉ ghép màn hình, bàn phím, chuột, sạc, tai nghe hoặc balo laptop.
- Model xếp hạng các ứng viên đã qua điều kiện thương mại. Model không được dùng để quyết định một điện thoại có phải laptop, váy hay phụ kiện hay không.

Kiểm tra cuối: 33 test tích hợp, 11 test storefront, 12 test Taobao native, 3 test cặp ảnh/tên và 5 test đánh giá đều qua. Chromium kiểm tra guest, hồ sơ đăng nhập, Lab, tìm kiếm, chi tiết, desktop 1440 px và mobile 390 px không có lỗi JavaScript hoặc tràn ngang. Service chạy một worker, `MemoryMax=1800M`, `MemorySwapMax=128M`; đỉnh quan sát sau suy luận đăng nhập khoảng 283 MB và không có OOM.

Các phần bên dưới ghi lại cả chế độ catalog Taobao native/storefront dùng để đối chiếu checkpoint; chúng không có nghĩa catalog tiếng Việt 2 triệu dòng đã được gắn nhãn đúng/sai bởi Taobao.

Bản này giữ giao diện Lumi với ảnh/tên tiếng Việt, ẩn mã sản phẩm khỏi thẻ và chi tiết, đồng thời thêm quy tắc chọn hàng trước khi hiển thị. Mục tiêu là tránh chuyển từ điện thoại sang váy/đồ gia dụng sau khi người dùng vừa chọn điện thoại.

## Quy tắc hiển thị

- Danh mục minh họa có 25 loại hàng nhỏ lấy từ metadata của chính ảnh/tên mẫu: điện thoại, laptop, máy tính bảng, tai nghe, loa, sạc/pin, ốp, phụ kiện quay chụp, các nhóm thời trang/làm đẹp/nhà cửa… Những nhãn này không phải nhãn Taobao được phục hồi từ embedding.
- Khi xem, lưu hoặc thêm giỏ, trang chủ tập trung vào loại hàng vừa quan tâm. Lựa chọn danh mục trực tiếp ưu tiên hơn ngữ cảnh tự động. Nút “Xem tất cả sản phẩm” trở lại khám phá rộng.
- Với tài khoản đăng nhập, ngữ cảnh lấy từ hành vi thật trên web. Khách chưa đăng nhập dùng sản phẩm đang xem trong phiên giao diện, không tạo tài khoản/lịch sử giả. Sau tải lại, ngữ cảnh của tài khoản được lấy lại từ DB; khách chưa đăng nhập không lưu lịch sử giả trên server.
- `catalog_settings.storefront_context.after_behavior_id` đánh dấu lúc triển khai. Các lượt xem mã/hình học trước đó không bị diễn giải lại thành sở thích đối với ảnh hàng hóa mới. Lịch sử Taobao gốc vẫn được MUSE đọc để chấm điểm như trước.
- Chi tiết chỉ gợi ý cùng loại hàng và loại toàn bộ bản sao ảnh/tên của sản phẩm đang xem. Giỏ dùng hợp các loại có trong giỏ và loại ảnh đã có. Sau mua dùng cùng loại với sản phẩm của đơn. Đây không phải mô hình học mua kèm hay bảo đảm tương thích phụ kiện.
- Mỗi ảnh/tên minh họa hiện một lần: giữ ID có điểm cao nhất trong tập hợp hợp lệ. Điểm bằng nhau lấy ID nhỏ hơn. Trang chủ bỏ sản phẩm minh họa đã tương tác thật sau mốc triển khai. Không dùng toàn bộ chuỗi ẩn danh để suy ra rằng người dùng đã xem hàng hóa minh họa.
- Khi hết lựa chọn cùng loại, giao diện có thông báo và nút chuyển danh mục; không tự lấp bằng hàng khác loại. Trường hợp ốp điện thoại chỉ có một mẫu là một ca được kiểm tra riêng.
- Mã ID/SKU không hiện ở thẻ và chi tiết mua sắm. Thứ hạng ID gốc có thể mở từ Chế độ Lab. Tìm kiếm/phân trang hiển thị các sản phẩm minh họa riêng biệt, thay vì nhiều trang lặp ảnh.

## MUSE và chất lượng

Không đổi checkpoint, ID, bốn đặc trưng gốc, ánh xạ vocabulary/SCL hay cách forward. MUSE tiếp tục chấm 8.192 ứng viên; các ID còn lại được sắp theo điểm giảm dần sau khi lọc ngữ cảnh. SCL ở chi tiết chỉ sắp các ứng viên cùng loại minh họa. Không cộng điểm danh mục vào P(click), không tạo demo_interest, không train lại.

**Danh sách trên web có thay đổi do lọc loại hàng và thẻ trùng. Điểm của từng ID không đổi.** Kiểm thử 65.536 điểm của tám hồ sơ trước/sau lớp hiển thị vẫn giữ nguyên; kiểm thử bổ sung xác nhận điểm của ID trả về đúng điểm model/cache và cosine đúng phép tính SCL gốc.

Các trường hợp kiểm tra trả cùng loại theo nhãn metadata; điều này kiểm chứng quy tắc lọc. Không được quy thành “model chính xác 100%”, AUC mới hay CTR tăng. AUC 62,02% hiện có vẫn là phép đo lấy mẫu Taobao của model gốc, trước lớp chọn hàng commerce. Chưa có đánh giá bằng phản hồi người mua đối với danh mục minh họa, sở thích chi tiết hoặc khả năng tương thích thiết bị.

## API và đối chiếu

- Giao diện gọi `/api/recommendations` với `presentation_policy=contextual`; chọn xem toàn bộ dùng `browse`. Chi tiết/giỏ/đơn vẫn giữ bộ lọc loại hàng khi dùng các chính sách commerce.
- `focus_product_id` chỉ định sản phẩm làm ngữ cảnh cho guest. Tài khoản dùng hành vi đã ghi. `display_category` là lựa chọn danh mục trực tiếp.
- `presentation_policy=original` trả thứ hạng ID gốc để đối chiếu trong Lab, chưa lọc loại hàng/thẻ trùng. Đây cũng là mặc định API để giữ hợp đồng kiểm chứng cũ; frontend commerce luôn gửi chính sách rõ ràng.
- `meta.merchandise_context` nêu nhãn/phạm vi/nguồn chọn loại, `duplicate_illustrations_removed` đếm số ID bị gom cùng ảnh, `empty_reason` nêu lý do hết lựa chọn. `model_used` và nhãn AI chỉ đúng khi có suy luận phù hợp.
- `/api/products?unique_products=true` tìm kiếm, lọc và phân trang trên các sản phẩm minh họa riêng biệt, tối đa 157 mẫu ảnh. API không bật tùy chọn này vẫn hỗ trợ duyệt catalog ID đầy đủ.
- So sánh hồ sơ trên UI dùng `browse`, bỏ ảnh trùng và tính phần giao theo sản phẩm minh họa. API so sánh mặc định giữ đơn vị ID gốc. So sánh chỉ đọc, không đổi phiên hay lịch sử.

Trạng thái trước/sau dùng sản phẩm minh họa để đếm thay đổi. Khi bộ lọc đổi loại, UI nói rõ “Gợi ý tiếp nối” thay vì coi việc đổi phạm vi là tăng độ chính xác. Khi đổi hồ sơ, ô tìm kiếm và nội dung cũ được khóa ngắn đến lúc chuyển xong, tránh gửi tìm kiếm/lượt xem trong lúc hồ sơ đang đổi.

## Kiểm thử

- **62 Python tests PASS**, 43,882 giây, `/tmp/lumi-context-unit-final.log`: giữ điểm gốc, cùng loại điện thoại/laptop/tai nghe/nước hoa/giày, bỏ ảnh trùng và ảnh mục tiêu, lọc danh mục thủ công, ngữ cảnh từ hành vi thật, giỏ đa loại, catalog riêng biệt, guest/ID không hợp lệ, fallback và trường hợp chỉ một sản phẩm.
- **Chromium commerce 12 nhóm luồng PASS**, `/tmp/lumi-context-commerce-browser-final.log`: tám hồ sơ, tìm kiếm/giá/phân trang mới, Lab, chi tiết, wishlist, giỏ, mua ngay/checkout, đặt/hủy đơn, địa chỉ/voucher, cold start, đánh giá sau giao, HTTP 503 và retry.
- **Chromium context 9 nhóm luồng PASS**, `/tmp/lumi-context-browser-final.log`: phone-only ở guest và tài khoản, giữ ngữ cảnh khi reload, chuyển sang laptop, danh mục thủ công, trở lại tất cả, raw IDs chỉ trong Lab, fallback giữ loại và bỏ nhãn AI, ba mẫu tai nghe riêng biệt, singleton rõ ràng. Home/feed kiểm tra 320/390/768/1440 px; không tràn ngang, mã SKU/TB, chữ Trung Quốc hoặc JavaScript page errors ở luồng kiểm tra khi Lab tắt.
- Tất cả thao tác tạo dữ liệu kiểm thử dùng DB bản sao `/tmp/lumi-context.db` hoặc DB tạm của unittest. Model/unit giới hạn 1600M RAM/128M swap; Chromium 512M/64M; một worker CPU, không reload và không huấn luyện.

## Áp dụng bản chính

Đã khởi động lại service `shopee-taobao.service` trên port 8000 với một worker CPU, MemoryMax=1600M, MemorySwapMax=128M. Backup trước thay đổi: `data/backups/before-context-20261016-023625.db`. Khởi tạo mốc ngữ cảnh sau behavior ID 8386; **25 bảng ngoài cấu hình giữ nguyên từng hàng**, bao gồm danh mục hiển thị, người dùng, giỏ, đơn và lịch sử. SQLite quick_check=ok, không lỗi foreign key.

Smoke trực tiếp bản chính chỉ đọc: model_ready=true, hàng xóm AI và feed tiếp nối của khách chỉ gồm điện thoại, không ảnh trùng/mã SKU hoặc chữ Trung Quốc; kiểm tra 320/390/768/1440 px không tràn ngang và không JavaScript page errors. So sánh hai hồ sơ dùng model thật và đếm giao theo sản phẩm minh họa đúng với danh sách. Guest vẫn chưa đăng nhập và không được tạo lịch sử giả.

Đã dừng server và browser kiểm thử. `memory.events` của service chính và preview không có OOM ở lần kiểm tra. Các con số này là kiểm tra chức năng, không phải thử tải production hoặc đo độ chính xác của danh mục minh họa. Kết quả máy đọc tại [context_verification.json](context_verification.json).
