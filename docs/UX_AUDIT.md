> **Cập nhật 16/10/2026:** bản hiện tại đã chuyển sang dữ liệu Taobao gốc và giao diện khám phá. Xem [TAOBAO_NATIVE.md](TAOBAO_NATIVE.md) cho pipeline, nguồn dữ liệu và quy tắc hiển thị hiện hành. Nội dung dưới lưu kiến trúc/đánh giá của bản danh mục minh họa trước chuyển đổi.

# Rà soát trải nghiệm và nghiệp vụ — 15/10/2026

Giao diện có nền tảng phù hợp cho demo mua sắm: header tìm kiếm rõ, phân nhóm nội dung, chi tiết sản phẩm, giỏ và tài khoản. Trước rà soát, khối quảng bá lấn gợi ý, chữ phụ nhỏ, danh sách dễ lặp ảnh và có các lỗi mua hàng cần sửa. Sau sửa, các luồng đã kiểm thử ổn định; chưa thể coi là sàn doanh nghiệp đã nghiệm thu.

## Những lỗi đã xử lý

| Vấn đề | Hành vi sau sửa |
|---|---|
| Mua ngay trộn với các món đã chọn trong giỏ | Báo giá/đặt riêng món và số lượng vừa chọn; giỏ cũ giữ nguyên |
| Đăng nhập làm mất món đang muốn mua | Tiếp tục ý định mua sau đăng nhập; hủy hộp thoại thì hủy ý định |
| Chỉ so tổng tiền, bỏ lọt trường hợp đổi món cùng giá | Fingerprint đầy đủ hàng, số lượng, địa chỉ và chi phí; trả 409 rồi hiển thị dữ liệu mới để xác nhận |
| Freeship cộng chung nhiều shop | Ngưỡng 150.000đ xét riêng từng shop, cùng một quy tắc ở giỏ/báo giá/gợi ý |
| Voucher vận chuyển bị tiêu dù không giảm thêm | Không cho áp dụng; giữ mã cho lần sau, giải thích trong lựa chọn voucher |
| Hết kho không bỏ chọn được | Cho bỏ chọn; chọn tất cả chỉ chọn các dòng đủ kho |
| Mua lại thêm dở giỏ khi một món thất bại | Thêm toàn bộ trong transaction, lỗi thì rollback |
| Reload màn hình thành công quay về checkout | URL chuyển sang Đơn mua, reload xem được đơn đã tạo |
| Địa chỉ vừa thêm chưa được chọn tại checkout | Tự chọn địa chỉ vừa lưu; kiểm tra lại báo giá |
| Dữ liệu bất đồng bộ có thể ghi đè màn hình mới | Guard theo route/user/request; khóa thao tác checkout trong lúc đặt; chặn bấm lặp trên cùng nút |
| Lỗi inference làm hỏng khối gợi ý; Lab dùng metrics người khác | Fallback phổ biến có nhãn; metrics giới hạn theo user |

## Vị trí gợi ý

| Vị trí | Mục đích và quy tắc |
|---|---|
| Trang chủ, trước danh mục | Khám phá theo lịch sử và nhu cầu; có nhãn AI khi dùng model, không lặp ảnh/tên kể cả xem thêm. Mobile ưu tiên gợi ý thay cho banner/lợi ích, thu gọn chọn nhu cầu. Khách chưa đăng nhập xem phổ biến |
| Cuối chi tiết sản phẩm | So sánh lựa chọn; ưu tiên cùng loại theo tên, cùng danh mục/giá 0,5–2 lần, xếp hạng SCL cosine, loại ảnh của món đang xem khi có lựa chọn khác |
| Sau tóm tắt giỏ hàng | Mua kèm có ngữ cảnh; cùng shop đang chọn, loại món/ảnh đã có trong giỏ, giới hạn giá theo giỏ và phần thiếu đến mốc freeship; có nút thêm nhanh và lý do. Không có món phù hợp thì ẩn |
| Thanh toán | Tập trung địa chỉ, ưu đãi, chi phí và xác nhận; không thêm khối mua kèm làm thay đổi đơn ngoài ý muốn |

Quy tắc thương mại chỉ điều chỉnh ứng viên/thứ tự; không sửa điểm MUSE. Raw ID, features và checkpoint chạy thật nhưng tên, ngành hàng, giá và ảnh Việt hóa là demo. Một số ảnh chỉ minh họa loại hàng, chưa đủ chính xác để dùng làm ảnh bán hàng thật. Muốn đánh giá gợi ý “đúng gu” trên hàng Việt cần dữ liệu sản phẩm đúng domain.

## Giao diện đã cải tiến

- Bỏ nội suy điểm model thành nhãn 82–99% phù hợp. Khách thấy “AI gợi ý”, lý do, số đo xếp hạng cặp có giải thích; tên MUSE, raw ID, P(click), cosine, latency và chỉ số chuyên sâu nằm trong Lab.
- Không dùng báo cáo thiếu nguồn/tọa độ lấy mẫu để khẳng định chất lượng. Đo lại thật trên 2.048 lượt hiển thị: AUC 0,620191; đây là mức vừa trên dữ liệu gốc, không phải tỷ lệ sản phẩm hợp gu trên danh mục tiếng Việt.
- Rà soát ảnh chụp thấy phụ kiện dùng nhầm ảnh sản phẩm chính và loa dùng ảnh tai nghe do quy tắc keyword. Khu vực gợi ý demo lọc từ bộ 1.000 tên biên soạn sẵn, kiểm tra họ ảnh theo loại hàng; 394 item đủ điều kiện metadata. Không xóa sản phẩm/raw ID/lịch sử/đơn hàng. Ảnh vẫn minh họa nhóm sản phẩm, chưa xác minh đúng từng thương hiệu/SKU/màu.
- Giữ nguồn gợi ý minh bạch: model lỗi hoặc không dùng thì bỏ nhãn AI và phần trăm; tài khoản mới có lời nhắc khởi đầu. Không tự đăng nhập lại sau đăng xuất, không suy đoán sở thích chỉ từ giới tính/năm sinh.
- Giới hạn ba thông báo nổi để không che danh sách khi đổi hồ sơ nhanh. Gợi ý AI có nút giải thích, nhóm nhu cầu cuộn ngang trên mobile, thẻ sản phẩm xuất hiện sớm trong màn hình.
- Đưa gợi ý lên trước ưu đãi; ẩn bớt banner phụ trên điện thoại, tăng cỡ chữ nội dung và trường nhập.
- Tóm tắt giỏ và nút mua xuất hiện trước khối mua kèm trên mobile; khối gợi ý dùng chiều rộng phù hợp, có lý do và thêm nhanh.
- Đổi “Flash Sale” có đồng hồ không gắn lịch khuyến mãi thành “Ưu đãi nổi bật”, dùng giá/giảm giá thực trong danh mục và chọn ảnh khác nhau.
- Hiển thị freeship đúng điều kiện; không gắn Mall/Freeship vô điều kiện cho mọi shop/sản phẩm.
- Kiểm tra home, chi tiết, giỏ, checkout ở 320/390/768/1440px. Không phát hiện tràn ngang trong các tình huống đã chạy.

## Thứ tự nên phát triển tiếp

1. **Dữ liệu và SKU:** ảnh thật khớp từng món; biến thể màu/size, tồn kho/giá theo SKU, ảnh theo biến thể, thuộc tính và bộ lọc đúng ngành. Đây là phần nâng độ thực tế rõ nhất.
2. **Đơn theo shop và vận hành:** checkout chung nhưng tạo đơn con cho từng shop; seller/admin có phân quyền, xác nhận từng đơn con, đóng gói, giao từng phần, trả hàng/hoàn tiền và nhật ký thao tác.
3. **Các kết nối thật:** thanh toán có webhook/idempotency/đối soát, phí và tracking từ hãng vận chuyển, xác minh email/SMS. Cần tài khoản dịch vụ và cấu hình của đơn vị vận hành.
4. **Tối ưu MUSE có đo lường:** log impression/click có request ID và vị trí hiển thị; đo Recall@K/NDCG/coverage/diversity, calibration và A/B test. Tách model service, registry/rollback khi cần mở rộng. Đánh giá trên metadata đúng domain trước khi kết luận hiệu quả.
5. **Hỗ trợ người mua:** chat theo đơn, trung tâm trợ giúp có ticket, đánh giá kèm ảnh đã kiểm duyệt và hành trình đổi trả.

Không nên thêm hàng loạt nút có vẻ giống Shopee nhưng thiếu nghiệp vụ phía sau. Hoàn thiện SKU → đơn con theo shop → vận hành/thanh toán thật tạo giá trị sử dụng lớn hơn việc thêm banner hoặc số liệu khuyến mãi mô phỏng.
