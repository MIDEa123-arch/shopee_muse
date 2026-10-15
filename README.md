# Shopee MUSE

Web mua sắm full-stack lấy cảm hứng từ Shopee, tích hợp suy luận Alibaba MUSE từ checkpoint đã huấn luyện. Giữ pattern của dự án: **FastAPI + SQLite + `app/routers` + `app/services` + `app/recommender` + HTML/CSS/JS SPA**.

Tài khoản, địa chỉ, giỏ hàng, voucher, Xu, đặt/hủy đơn, wishlist, đánh giá và lịch sử tương tác được lưu thật trong database. Tiền ví, cước, giao nhận, rating/lượng bán mẫu và thông tin thương mại phục vụ demo. Không liên kết với Shopee.

## Chạy trên máy hiện tại

```bash
cd /home/midea/Projects/shopee_muse
/home/midea/Projects/demo_env/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mở **http://localhost:8000**. Database hiện tại đã được nâng cấp; **không cần reset dữ liệu**. Model khởi động có thể mất vài giây đến vài chục giây để đọc và warm-up. API tài liệu: http://localhost:8000/api/docs.

Chọn hồ sơ ở thanh **Không gian trải nghiệm** để thử 8 tài khoản. Tài khoản mẫu cũ vẫn dùng mật khẩu `123456`; đăng nhập thành công sẽ nâng cấp hash SHA-256 cũ sang PBKDF2. Tài khoản tạo mới qua script seed dùng mật khẩu `Demo12345!`. Tài khoản khách mới có ví/Xu bằng 0.

## Cài đặt máy mới

Python 3.11+ được khuyến nghị. Đặt checkpoint vào `checkpoints/` và dữ liệu Taobao-MM vào thư mục do `MUSE_DATASET_DIR` chỉ định.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export MUSE_DATASET_DIR=/duong/dan/TaoBao_dataset
python scripts/init_database.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`init_database.py` chỉ seed khi danh mục trống; không DROP bảng và không xóa dữ liệu nghiệp vụ. Nếu không có dataset, script tạo danh mục mẫu với ID tổng hợp; web ghi rõ fallback và không có điểm click MUSE. Nếu database đã có sản phẩm nhưng chưa có model features:

```bash
python scripts/prepare_muse.py
```

Các file cần cho suy luận thật:

```text
checkpoints/muse_full_training_dense.ckpt
checkpoints/muse_full_training_sparse.ckpt
$MUSE_DATASET_DIR/feature_map/*_sorted_map.npy
$MUSE_DATASET_DIR/feature_map/150_2_180_sorted_map_p90.npy
$MUSE_DATASET_DIR/feature_map/scl_emb_int8_p90_keys.npy
$MUSE_DATASET_DIR/feature_map/scl_emb_int8_p90_values.npy
```

Import lần đầu cần thêm `raw/item_features.parquet` và `test/test-shard-000000.parquet`. Dữ liệu và checkpoint không commit Git. Không sửa hoặc xóa bảng ID map: thứ tự vocab phải khớp checkpoint.

## Tính năng

- Trang chủ, banner slider, danh mục, ưu đãi, tìm kiếm tiếng Việt/không dấu, lọc giá/tỉnh, sắp xếp, phân trang, chi tiết và sản phẩm tương tự.
- Đăng nhập/đăng ký/đăng xuất; sửa hồ sơ và ảnh đại diện có sẵn; đổi mật khẩu; OTP khôi phục demo có hạn dùng và giới hạn lần thử.
- Sổ địa chỉ với 34 tỉnh/thành và một địa chỉ mặc định. Đã sửa Bình Dương → Hưng Yên theo danh sách hành chính hiện hành; tham chiếu cũ của Bình Dương được chuyển về TP.HCM.
- Giỏ hàng theo shop, chọn sản phẩm, sửa số lượng, kiểm tồn kho; lưu voucher; áp dụng ưu đãi, Xu và phí ship tại server.
- Đặt hàng COD/ví mô phỏng, mã SPX, chống đặt trùng, transaction kiểm kho/trừ tiền; hủy đơn chờ xác nhận và hoàn quyền lợi đúng một lần.
- Theo dõi đơn, mua lại, đánh giá sau nhận hàng, yêu thích và thông báo. Chuyển trạng thái giao hàng chỉ là thao tác demo có nhãn.
- MUSE ranking trang chủ; GSU/SCL cosine tại chi tiết; mua kèm theo giá và ranking tại giỏ. Click/thêm giỏ/mua hàng cập nhật lịch sử và suy luận lại.
- **MUSE Lab**: raw ID 64-bit chính xác, chuỗi 1.000 hành vi, P(click)/cosine, số ứng viên, coverage, latency đo thực và nhật ký.

## Kịch bản trình diễn

1. Chọn một trong 8 hồ sơ; xem mục Gợi ý hôm nay.
2. Bật **MUSE Lab**, kiểm tra `CHECKPOINT LOADED`, raw user ID và số hành vi.
3. Mở sản phẩm để ghi thêm click; đóng chi tiết và xem lại điểm/thứ hạng. Không có cơ chế ép danh sách đổi theo ngành hàng tiếng Việt.
4. Chọn **Soi lịch sử chuỗi 1K**: phân biệt `imported_click` từ test shard và tương tác mới trên web.
5. Thêm vào giỏ, chọn địa chỉ, voucher/Xu, thanh toán demo; mở Đơn mua và hủy để kiểm chứng hoàn tiền/tồn kho, hoặc dùng nút `[Demo]` để minh họa giao hàng và đánh giá.

Hai checkpoint và model chạy thật. Tên/giá/ngành hàng tiếng Việt cùng ảnh Unsplash là metadata minh họa được gắn với raw ID, **không phải ảnh và tên gốc Taobao**. Có nhiều sản phẩm dùng chung ảnh mẫu, không tuyên bố 1.000 ảnh độc nhất. Chỉ số AUC 0.644728, GAUC 0.614794 và loss 0.383716 lấy từ báo cáo bạn cung cấp, chưa chạy lại evaluation ở web. Mọi latency trong Lab đều được đo, không gán hằng số 4 ms.

## Kiểm thử

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Integration test tạo bản sao SQLite trong thư mục tạm, không đặt hàng hoặc sửa số dư database chính. Kiểm tra quyền sở hữu, OTP/session, validation, chế độ production, số tiền, rollback, idempotency, hoàn tiền, tranh mua sản phẩm cuối và ảnh hưởng của tương tác lên model.

Browser smoke test **phải trỏ vào server dùng database riêng**:

```bash
# Sao chép nhất quán, kể cả khi SQLite đang dùng WAL
python -c "import sqlite3; sqlite3.connect('data/shopee_muse.db').backup(sqlite3.connect('/tmp/muse-browser.db'))"
DATABASE_PATH=/tmp/muse-browser.db python -m uvicorn app.main:app --port 8011
# Terminal khác
python -m playwright install chromium
TEST_BASE_URL=http://127.0.0.1:8011 python tests/browser_smoke.py
```

Ảnh kiểm thử mặc định lưu ở `/tmp/shopee-muse-preview`. Script trình duyệt thực hiện đặt/hủy đơn trên database thử, kiểm tra desktop/mobile và lỗi JavaScript.

## Cấu hình vận hành

| Biến môi trường | Mặc định |
|---|---|
| `DATABASE_PATH` | `data/shopee_muse.db` dưới repo |
| `MUSE_DATASET_DIR` | `~/TaoBao_dataset` |
| `MUSE_CHECKPOINT_DIR` | `checkpoints/` dưới repo |
| `DEMO_MODE` | `true` |
| `SECURE_COOKIES` | `false` cho HTTP local |

`.env.example` mô tả cấu hình; app không tự load file `.env`, hãy export biến hoặc cấu hình qua process manager. Khuyến nghị chạy một worker cho demo CPU/SQLite.

Trước khi dùng dữ liệu khách thật: đặt `DEMO_MODE=false`, bật HTTPS và `SECURE_COOKIES=true`. Chế độ này chặn đổi hồ sơ không mật khẩu, OTP giả lập, debug và ví demo. Cần tích hợp cổng thanh toán, OTP thật, hãng vận chuyển, seller/admin, trả hàng, đối soát, backup/monitoring và dữ liệu hàng hóa đúng domain. Không coi bản demo là hệ thống doanh nghiệp đã được nghiệm thu.

Xem [phân tích kiến trúc, tính đúng đắn của MUSE và phần cần làm để vận hành thật](docs/ARCHITECTURE.md).

## Nguồn và giấy phép MUSE

[Bài báo arXiv:2512.07216](https://arxiv.org/abs/2512.07216) · [MUSE chính thức](https://github.com/alimama-tech/MUSE). Phần forward được điều chỉnh import từ upstream commit `85eea1587164cd24eb6223d3d0243aca955af980`; giấy phép Apache-2.0 và ghi nhận nguồn trong `app/recommender/upstream/`. Phần phục vụ CPU/SQLite/SPA được viết cho dự án này.
