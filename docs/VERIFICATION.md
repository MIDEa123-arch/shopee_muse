# Kết quả kiểm chứng — 15/10/2026

- **16 integration tests: PASS.** Database được sao chép vào thư mục tạm, không tạo đơn hoặc thay đổi số dư database chính. Có kiểm tra checkpoint thật, cập nhật điểm sau click, tranh mua món cuối, idempotency, báo giá thay đổi, rollback, hoàn quyền lợi, validation, session/OTP, phân quyền và chặn chế độ demo khi tắt DEMO_MODE.
- **14 browser flows: PASS** trên Chromium, viewport desktop 1440px và mobile 390px: trang chủ khách, đổi hồ sơ, MUSE Lab, chi tiết, thêm giỏ, checkout, đặt hàng, hủy đơn, tìm kiếm, sắp giá, form tài khoản/ảnh đại diện, form địa chỉ, trang chủ mobile và modal sản phẩm mobile. Không phát sinh JavaScript page errors; không tràn ngang trang hoặc modal.
- `node --check static/js/app.js`, Python `compileall` và `git diff --check`: PASS.
- Khởi tạo database mới có dataset, chạy lại không reset, và seed fallback khi không có dataset: PASS.
- Database chính sau triển khai: 1.000 sản phẩm, 8 hồ sơ, 8.000 hành vi nhập thật, 1.000 bộ feature item, 8 bộ feature user. Chưa phát sinh đơn mua hay giỏ hàng do kiểm thử trong database chính.
- SCL 128 chiều và cả hai checkpoint được nạp. Lần đo tham khảo trên 1.000 ứng viên: khoảng 90–132 ms inference và 107–160 ms dịch vụ; thay đổi theo tải và cache, không phải benchmark hoặc SLO.
- Ảnh minh họa được cache local; sửa lỗi danh mục cũ chọn lặp template và ảnh không khớp tên. Có 32 mẫu tên thương mại và 30 ảnh sản phẩm dùng chung trong 1.000 item. Không có 1.000 ảnh Taobao độc nhất.

Lệnh tái hiện nằm trong README. Screenshot của lần chạy lưu tại `/tmp/shopee-muse-preview/`. Bộ browser test dùng database `/tmp/shopee-muse-verification.db`, không dùng database chính.

Chưa kiểm chứng tải production, tích hợp thanh toán/OTP/vận chuyển thật, hoặc đánh giá lại AUC/GAUC trên toàn tập test. Các phần này được nêu trong `ARCHITECTURE.md`.
