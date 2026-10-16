# Chạy Lumi trên Windows

Hướng dẫn dùng Windows 10/11 64-bit, PowerShell và Python 3.11 64-bit. Không cần Node.js hoặc GPU. Dùng lại model đã huấn luyện, không train lại.

## 1. Tải mã nguồn và cài môi trường

Cài [Git for Windows](https://git-scm.com/downloads/win) và [Python 3.11](https://www.python.org/downloads/release/python-3119/). Khi cài Python, chọn **Add python.exe to PATH**. Mở PowerShell rồi chạy:

```powershell
git clone https://github.com/MIDEa123-arch/shopee_muse.git
cd shopee_muse
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install "torch>=2.6,<3" --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Không cần activate môi trường: các lệnh trên gọi thẳng Python trong `.venv`. Không copy `.venv` từ Linux sang Windows; phải tạo mới bằng các lệnh này.

## 2. Mang database và model sang Windows

Git chỉ chứa mã nguồn, giao diện và ảnh nhỏ. Database, checkpoint và mảng đặc trưng nhiều GB được giữ ngoài Git. **Chỉ clone repo chưa đủ để chạy lại bản demo có dữ liệu hiện tại.**

Từ máy Linux hiện tại, copy các file sau sang máy Windows qua ổ cứng, USB hoặc thư mục chia sẻ:

| Nguồn trên máy Linux | Đích trong thư mục repo trên Windows |
| --- | --- |
| `data/shopee_muse.db` | `data\shopee_muse.db` |
| `checkpoints/muse_full_training_dense.ckpt` | `checkpoints\muse_full_training_dense.ckpt` |
| `checkpoints/muse_full_training_sparse.ckpt` | `checkpoints\muse_full_training_sparse.ckpt` |
| Các file cần thiết trong `data/feature_map/` | `data\feature_map\` |

Trước khi copy SQLite, dừng server Linux bằng `systemctl --user stop shopee-taobao.service` và đóng các công cụ đang ghi database. Nếu còn `shopee_muse.db-wal` hoặc `shopee_muse.db-shm`, giữ cả bộ file cùng tên khi copy. Sau khi copy xong có thể bật lại server Linux bằng `systemctl --user start shopee-taobao.service`. Không copy riêng file `.db` đang có tiến trình ghi.

Các file `feature_map` cần cho suy luận:

```text
129_1_sorted_map.npy
130_1_sorted_map.npy
130_2_sorted_map.npy
130_3_sorted_map.npy
130_4_sorted_map.npy
130_5_sorted_map.npy
150_2_180_sorted_map_p90.npy
151_2_180_sorted_map.npy
213_sorted_map.npy
214_sorted_map.npy
scl_emb_int8_p90_keys.npy
scl_emb_int8_p90_values.npy
```

Không cần copy `150_2_180_sorted_map.npy` bản đầy đủ, các parquet train/test hoặc toàn bộ dataset để phục vụ web khi đã có database và các file trên. Các file này phải thuộc đúng checkpoint đang dùng; không tự tạo lại map. Chuẩn bị ít nhất 15 GB ổ trống cho dữ liệu/model, cộng thêm dung lượng cài Python và thư viện.

Nếu đặt file ở ổ khác, cấu hình ngay trong cửa sổ PowerShell sẽ chạy server:

```powershell
$env:DATABASE_PATH = 'D:\LumiData\shopee_muse.db'
$env:MUSE_DATASET_DIR = 'D:\TaoBao_dataset'
$env:MUSE_CHECKPOINT_DIR = 'D:\LumiData\checkpoints'
```

`MUSE_DATASET_DIR` phải là thư mục **chứa** `feature_map`, không trỏ trực tiếp vào `feature_map`. Khi đặt file theo cấu trúc mặc định trong repo, bỏ qua ba biến này.

## 3. Chạy web

Tại thư mục repo, chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_windows.ps1
```

Mở **http://localhost:8000**. Lệnh `Bypass` chỉ áp dụng cho tiến trình PowerShell này. Script kiểm tra file trước khi mở server, sử dụng một worker CPU và không bật reload. Dừng bằng **Ctrl+C**.

Đổi cổng nếu cổng 8000 đang được ứng dụng khác sử dụng:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_windows.ps1 -Port 8001
```

Hoặc chạy trực tiếp sau khi đã kiểm tra đủ file:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

## 4. Kiểm tra model và giao diện

Mở cửa sổ PowerShell thứ hai:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

Kết quả cần có `status: ok` và `model_ready: True`. `model_ready: False` nghĩa web đang dùng cách xếp hạng dự phòng; xem cửa sổ server để tìm file thiếu hoặc lỗi ánh xạ checkpoint. Có thể chọn một hồ sơ mua sắm rồi bật **Chế độ Lab** để kiểm tra lịch sử và điểm model. Các thuật ngữ này được ẩn trong chế độ mua sắm thường.

Thử ô tìm kiếm: bấm vào ô để mở gợi ý, bấm khoảng trống để đóng, nhấn **Esc** để đóng, hoặc dùng **Tab** để chuyển sang nút bên ngoài. Bấm lại ô tìm kiếm sẽ mở gợi ý trở lại.

## 5. Chạy nhẹ và xử lý lỗi

- Chạy một cửa sổ server, một worker; không thêm `--reload` hoặc nhiều worker. Không chạy script huấn luyện, tạo lại catalog hay toàn bộ test nặng chỉ để mở web.
- Mở Task Manager để theo dõi RAM lần đầu. Model đọc mảng qua memory mapping; RAM thực tế trên Windows phụ thuộc hệ điều hành và dữ liệu. Mức RAM đo trên Linux không phải cam kết cho Windows. Script không đặt trần RAM cứng trên Windows.
- Nếu `py` không được nhận diện, mở lại PowerShell sau khi cài Python; kiểm tra bằng `py -0p` hoặc dùng đường dẫn đầy đủ tới Python 3.11.
- Nếu PyTorch báo thiếu DLL, cài Microsoft Visual C++ Redistributable 2015–2022 x64 từ Microsoft rồi mở lại PowerShell.
- Nếu báo thiếu file, copy đúng các file ở bước 2. Không chạy lệnh tạo database rỗng để thay cho database demo hiện tại.
- Nếu model nạp lỗi, kiểm tra đủ checkpoint và 12 file `.npy` đúng bộ. Có thể dùng WSL2/Ubuntu với hướng dẫn Linux trong README nếu môi trường Windows gặp lỗi thư viện.
- Cập nhật mã bằng `git pull`, rồi chạy lại lệnh cài `requirements.txt` nếu có thay đổi thư viện. Dừng và chạy lại server sau khi cập nhật.

Script PowerShell được cung cấp cho Windows; phiên làm việc phát triển hiện tại chạy Linux, nên chưa kiểm chứng thực thi trên máy Windows thật.

Tham khảo chính thức: [Python trên Windows](https://docs.python.org/3.11/using/windows.html), [cài PyTorch CPU](https://docs.pytorch.org/get-started/locally/), [Execution Policy của PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies).
