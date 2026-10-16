# CẨM NANG TOÀN DIỆN: HUẤN LUYỆN MÔ HÌNH MUSE TRÊN GOOGLE COLAB PRO & ĐỀ CƯƠNG TIỂU LUẬN BIG DATA

> **Tài liệu hướng dẫn dành cho người mới bắt đầu**<br>
> **Môi trường huấn luyện**: Google Colab Pro (GPU NVIDIA A100 / V100) + Google Drive<br>
> **Dự án**: Hệ thống gợi ý sản phẩm thương mại điện tử đa phương thức (Multimodal Recommendation)<br>
> **Bộ dữ liệu**: Taobao-MM (139 GB) trên Google Drive | **Mô hình cốt lõi**: MUSE (Alimama / Alibaba)

---

## PHẦN 1: HƯỚNG DẪN QUY TRÌNH HUẤN LUYỆN TRÊN GOOGLE COLAB PRO

### 1. Chuẩn bị môi trường trên Colab Notebook

Khi bạn mở một cuốn Google Colab Notebook mới (đã bật gói Colab Pro), các bước thiết lập đầu tiên diễn ra như sau:

#### Bước 1.1: Kết nối Google Drive vào Colab
Chạy ô lệnh đầu tiên để mount toàn bộ dữ liệu từ Google Drive của bạn sang máy ảo Colab:
```python
from google.colab import drive
drive.mount('/content/drive')
```
*Sau khi chạy, toàn bộ thư mục dữ liệu Taobao của bạn sẽ nằm tại:*<br>
📁 `/content/drive/MyDrive/TaoBao_dataset/`

#### Bước 1.2: Kiểm tra GPU khủng của Colab Pro
```bash
!nvidia-smi
```
*(Colab Pro sẽ cấp phát GPU chuyên dụng như **NVIDIA A100** hoặc **V100**. Với GPU A100 40GB/80GB VRAM, tốc độ huấn luyện sẽ cực kỳ nhanh).*

#### Bước 1.3: Tải mã nguồn MUSE về máy ảo Colab
```bash
!git clone https://github.com/alimama-tech/MUSE.git
%cd /content/MUSE
!pip install -q pyarrow duckdb
```

---

### 2. Các file quan trọng trong repo MUSE và công dụng của từng file

Trong thư mục `/content/MUSE`, bạn sẽ làm việc với các file chính sau:

| Tên File / Thư mục | Vai trò và Ý nghĩa | Công việc thực hiện trên Colab |
| :--- | :--- | :--- |
| **`dataset.py`** *(hoặc `dataloader.py`)* | **Người vận chuyển dữ liệu** | Đọc các file Parquet và `.npy` từ Google Drive, đóng gói thành từng batch nạp vào GPU A100. |
| **`models/muse.py`** | **Bộ não của hệ thống** | Chứa kiến trúc mạng neural MUSE: tầng Multimodal Search Layer, Attention đa phương thức và tầng MLP dự đoán. |
| **`models/din.py`, `sim.py`** | **Mô hình đối chứng (Baselines)** | Các mô hình thế hệ cũ viết sẵn để chạy đối chứng so sánh với MUSE trong bài báo cáo. |
| **`train.py`** *(hoặc `main.py`)* | **Nhạc trưởng điều khiển** | Kịch bản chính bạn sẽ bấm chạy trên Colab. Kết nối data với model, thiết lập số epoch, batch size và ghi nhận Loss/AUC. |
| **`config.py`** *(hoặc `params.yaml`)* | **Bảng cài đặt đường dẫn** | Nơi bạn khai báo đường dẫn trỏ vào thư mục trên Google Drive. |

---

### 3. Quy trình cấu hình & Huấn luyện từng bước trên Colab

#### Bước 3.1: Khai báo đường dẫn dữ liệu từ Google Drive
Mở file cấu hình `config.py` (hoặc truyền qua cờ lệnh trong `train.py`), chỉnh sửa đường dẫn trỏ thẳng vào Google Drive:
* **Thư mục train**: `/content/drive/MyDrive/TaoBao_dataset/train/`
* **Thư mục test**: `/content/drive/MyDrive/TaoBao_dataset/test/`
* **Thư mục feature_map**: `/content/drive/MyDrive/TaoBao_dataset/feature_map/`
* **Thư mục lưu Checkpoint**: `/content/drive/MyDrive/TaoBao_dataset/checkpoints/`

#### Bước 3.2: Mẹo Vàng Tối ưu Tốc độ đọc (I/O) trên Colab Pro
Google Drive kết nối với Colab qua giao thức mạng. Để GPU A100 không phải "ngồi chờ" mạng tải từng file, bạn nên copy các shard dự định train hôm nay sang ổ SSD siêu tốc của Colab:
```bash
# Tạo thư mục tạm trên ổ SSD NVMe của Colab
!mkdir -p /content/local_data/train

# Copy feature_map (chỉ copy 1 lần)
!cp -r /content/drive/MyDrive/TaoBao_dataset/feature_map /content/local_data/

# Copy 5 đến 10 shard train để chạy thử hôm nay
!cp /content/drive/MyDrive/TaoBao_dataset/train/train-shard-00000[0-5].parquet /content/local_data/train/
```
*(Sau đó trỏ đường dẫn train trong code về `/content/local_data/` để đạt tốc độ đọc cực đại 2–3 GB/s).*

#### Bước 3.3: Chạy thử nghiệm trên tập nhỏ (Dry-run)
* Trong ô lệnh Colab, chạy thử 1 epoch ngắn với 1–2 shard:
```bash
!python train.py --data_dir /content/local_data --epochs 1 --batch_size 1024
```
* **Mục tiêu**: Xác nhận code đọc file mượt mà, GPU A100 hoạt động 100% công suất, hàm Loss giảm đều và không phát sinh lỗi tràn bộ nhớ.

#### Bước 3.4: Huấn luyện chính thức theo từng đợt
* Khi chạy thử đã ổn, bạn tăng số lượng shard (ví dụ 10 đến 30 shard).
* Do sử dụng GPU A100, bạn có thể tự tin đặt `batch_size = 1024` hoặc `2048` để rút ngắn thời gian huấn luyện xuống chỉ còn vài chục phút.

---

### 4. Cơ chế lưu Checkpoint an toàn trên Google Drive & Huấn luyện tiếp (Fine-tune)

#### Checkpoint được lưu ở đâu?
* Nhờ trỏ thư mục lưu về Google Drive:<br>
  📁 `/content/drive/MyDrive/TaoBao_dataset/checkpoints/best_model.pth`
* 👉 **Ưu thế tuyệt đối**: Cứ khi nào mô hình đạt chỉ số AUC kỷ lục, file trọng số sẽ được ghi đè thẳng lên Google Drive của bạn. **Dù Colab bị ngắt kết nối hay hết phiên làm việc, file model không bao giờ bị mất!**

#### Cách nạp Checkpoint để Train tiếp (Fine-tuning):
Hôm sau bạn mở Colab lên muốn train tiếp trên 10 shard mới:
1. Mount Google Drive như bình thường.
2. Trong lệnh chạy `train.py`, thêm cờ nạp checkpoint cũ:
```bash
!python train.py \
    --resume_checkpoint /content/drive/MyDrive/TaoBao_dataset/checkpoints/best_model.pth \
    --lr 0.0001
```
3. Mô hình sẽ nạp lại toàn bộ kiến thức cũ từ Drive và tiếp tục học trên các shard mới với tốc độ học thấp (`lr = 0.0001`), tích lũy thêm tri thức mà không bị học lại từ con số 0.

---
---

## PHẦN 2: ĐỀ CƯƠNG CHI TIẾT VIẾT TIỂU LUẬN / BÁO CÁO HỌC THUẬT

### 📌 TÊN ĐỀ TÀI GỢI Ý:
> **"Nghiên cứu và Triển khai Hệ thống Gợi ý Sản phẩm Đa phương thức dựa trên Kiến trúc Dữ liệu lớn Taobao-MM và Mô hình MUSE trên Nền tảng Điện toán Đám mây Google Colab Pro"**

---

### CHƯƠNG 1: TỔNG QUAN VÀ ĐẶT VẤN ĐỀ
1. **Bối cảnh thực tế**:
   * Sự bùng nổ của các sàn thương mại điện tử (Shopee, Lazada, Taobao).
   * Tầm quan trọng sống còn của hệ thống gợi ý trong việc cá nhân hóa trải nghiệm và tối ưu hóa doanh thu.
2. **Hạn chế của các hệ thống gợi ý truyền thống**:
   * Vấn đề "Mù hình ảnh" (ID-only): Các thuật toán cũ chỉ biết ID sản phẩm, không hiểu được màu sắc, kiểu dáng, phong cách.
   * Vấn đề "Sản phẩm mới" (Cold-start): Khi một món đồ mới lên kệ chưa có ai bấm mua, các hệ thống cũ hoàn toàn không thể gợi ý được.
3. **Mục tiêu nghiên cứu của đề tài**:
   * Khai thác sức mạnh của dữ liệu đa phương thức (Multimodal: hình ảnh + thuộc tính văn bản).
   * Triển khai mô hình gợi ý theo chuỗi hành vi dài hạn (MUSE).
   * Ứng dụng hạ tầng đám mây Google Colab Pro và Google Drive để huấn luyện dữ liệu lớn.
   * Xây dựng ứng dụng Web demo gợi ý sản phẩm thời gian thực.

---

### CHƯƠNG 2: KIẾN TRÚC DỮ LIỆU LỚN VÀ QUY TRÌNH TIỀN XỬ LÝ (BIG DATA PIPELINE)
*Đây là chương trọng tâm giúp ghi điểm cao nhất môn Big Data.*

1. **Khảo sát bộ dữ liệu Taobao-MM (139 GB)**:
   * Giới thiệu quy mô tập dữ liệu từ nền tảng Taobao thực tế.
   * Cấu trúc tập dữ liệu thô ban đầu (`raw/` trên Drive):
     * `train_samples.parquet`: Log hành vi click chuột thời gian thực.
     * `train_user_features.parquet`: Bảng đặc trưng nhân khẩu học người dùng.
     * `item_features.parquet`: Bảng thuộc tính sản phẩm (danh mục, cửa hàng).
     * `scl_embedding_int8_p90.parquet`: Vector ảnh đa phương thức gốc.
2. **Thách thức kỹ thuật của Dữ liệu thô**:
   * Dữ liệu phân tán nhiều bảng riêng lẻ. Nếu thực hiện phép `JOIN` trực tiếp lúc train sẽ gây nghẽn băng thông I/O và tràn bộ nhớ RAM.
3. **Quy trình tiền xử lý dữ liệu (ETL Pipeline)**:
   * **Xử lý phân tán (Distributed Join & Sharding)**: Sử dụng công nghệ Big Data phân tán (tương đương Apache Spark) để join sẵn các bảng người dùng - sản phẩm - lịch sử click, xuất ra các file phân mảnh định dạng cột **Parquet** (`train-shard-*.parquet`).
   * **Trích xuất đặc trưng Đa phương thức (SCL - Supervised Contrastive Learning)**: Ứng dụng mô hình thị giác máy tính mã hóa ảnh sản phẩm thành các vector ngữ nghĩa.
   * **Tối ưu hóa tài nguyên (Quantization INT8 & Percentile 90)**: Lượng tử hóa vector từ số thực 32-bit (`float32`) về số nguyên 8-bit (`int8`), giảm **75% dung lượng bộ nhớ** mà vẫn bảo toàn độ chính xác.
   * **Đánh chỉ mục O(1) bằng Sorted Map**: Chuyển đổi ID chuỗi rời rạc thành chỉ số nguyên liên tục `[0, N]` lưu dưới định dạng nhị phân `.npy` để tra cứu trong thời gian $O(1)$.
4. **Thành phẩm thu được**:
   * Thư mục `train/` (49 GB), `test/` (15 GB) và `feature_map/` (6.7 GB) lưu trữ trên Google Drive hoàn toàn tối ưu hóa cho huấn luyện Deep Learning.

---

### CHƯƠNG 3: CƠ SỞ LÝ THUYẾT VÀ KIẾN TRÚC MÔ HÌNH MUSE
1. **Bài toán khai thác chuỗi hành vi dài hạn (Lifelong User Interest Modeling)**:
   * Tại sao lịch sử xem hàng trong quá khứ phản ánh chính xác xu hướng mua sắm tiếp theo.
2. **Khảo sát các mô hình đối chứng (Baselines)**:
   * **DIN (Deep Interest Network)**: Cơ chế chú ý (Attention) trên hành vi ngắn hạn.
   * **SIM (Search-based Interest Model)**: Tìm kiếm hành vi dài hạn nhưng chỉ dựa trên mã định danh ID.
3. **Kiến trúc chi tiết mô hình MUSE (MUltimodal SEarch)**:
   * **Tầng trích xuất ứng viên tương đồng (Search Layer)**: Sử dụng vector SCL của sản phẩm mục tiêu để truy vấn ngược lại các sản phẩm có phong cách/hình ảnh tương tự trong quá khứ của người dùng.
   * **Tầng Attention Đa phương thức**: Tính toán trọng số quan tâm của người dùng đối với phong cách sản phẩm đó ở thời điểm hiện tại.
   * **Tầng Dự đoán (Prediction Layer / MLP)**: Kết hợp vector sở thích với đặc trưng nhân khẩu học để xuất ra xác suất Click-Through Rate (CTR).

---

### CHƯƠNG 4: THỰC NGHIỆM VÀ ĐÁNH GIÁ TRÊN GOOGLE COLAB PRO
1. **Thiết lập môi trường thực nghiệm Cloud**:
   * Phần cứng đám mây: Google Colab Pro với GPU **NVIDIA A100-SXM4-40GB** / **V100-16GB**, RAM hệ thống High-RAM (51 GB).
   * Lưu trữ: Google Drive kết nối qua Google Cloud FUSE.
   * Phần mềm & Thư viện: PyTorch (CUDA 12.x), PyArrow, DuckDB.
2. **Các độ đo đánh giá hiệu năng (Metrics)**:
   * **AUC (Area Under the ROC Curve)**: Độ đo tiêu chuẩn vàng trong bài toán Recommendation.
   * **Logloss (Binary Cross-Entropy Loss)**: Đo lường mức độ sai lệch của xác suất dự đoán.
3. **Kế hoạch huấn luyện theo chặng (Phased Training Strategy)**:
   * Chặng 1: Huấn luyện thử nghiệm kiểm tra pipeline đọc Parquet.
   * Chặng 2: Huấn luyện chính thức với GPU A100 và lưu Best Checkpoint về Google Drive.
   * Chặng 3: Tinh chỉnh sâu (Fine-tuning) với Learning Rate thấp.
4. **Phân tích kết quả thực nghiệm**:
   * Biểu đồ đường cong hàm mất mát (Loss Curve) qua các epoch.
   * Bảng so sánh chỉ số AUC giữa mô hình MUSE so với các baseline (DIN, SIM) để làm rõ giá trị vượt trội của thông tin hình ảnh đa phương thức.

---

### CHƯƠNG 5: TRIỂN KHAI HỆ THỐNG DEMO THỜI GIAN THỰC (SYSTEM SERVING & DEMO)
1. **Kiến trúc tổng thể của Ứng dụng Demo**:
   * Mô hình 3 tầng: Giao diện người dùng (UI) $\rightarrow$ Backend suy luận (Inference Engine) $\rightarrow$ Cơ sở dữ liệu sản phẩm (Database).
2. **Thiết kế Cơ sở dữ liệu nhẹ (Lightweight Database)**:
   * Sử dụng file `raw/item_features.parquet` (chứa hơn 4.1 triệu sản phẩm).
   * Nạp vào **SQLite** hoặc **DuckDB** để quản lý danh mục mặt hàng, tên gọi, ngành hàng.
3. **Quy trình xử lý gợi ý thời gian thực (Real-time Recommendation Flow)**:
   * Người dùng thao tác trên web (chọn tài khoản hoặc click xem một vài sản phẩm mẫu).
   * Backend lấy chuỗi hành vi, gọi checkpoint mô hình MUSE (được train từ Colab) để chấm điểm dự đoán.
   * Truy vấn Database lấy thông tin Top 10 sản phẩm cao điểm nhất và hiển thị lên web.
4. **Giao diện người dùng (Streamlit / Gradio)**:
   * Trực quan hóa danh sách sản phẩm gợi ý tương tự như giao diện "Gợi ý hôm nay" của Shopee.
   * Có thể khởi chạy trực tiếp trên Colab (dùng link Public Gradio `share=True`) hoặc chạy trên máy cục bộ.

---

### CHƯƠNG 6: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN
1. **Các kết quả đạt được của đề tài**:
   * Nắm vững quy trình xử lý dữ liệu lớn (Big Data ETL) từ dữ liệu thô sang dữ liệu tối ưu.
   * Làm chủ kỹ năng huấn luyện mô hình quy mô lớn trên nền tảng đám mây Google Colab Pro.
   * Huấn luyện thành công mô hình gợi ý đa phương thức tiên tiến (MUSE).
   * Xây dựng thành công ứng dụng demo hoàn chỉnh chạy trực tiếp từ mô hình học máy.
2. **Hạn chế và Hướng nghiên cứu tiếp theo**:
   * Triển khai cụm tìm kiếm vector quy mô lớn (FAISS / Milvus) trên hạ tầng phân tán.
   * Mở rộng thêm dữ liệu video ngắn (Short-form video recommendation như TikTok Shop).

---
---

## PHẦN 3: BẢN ĐỒ CÔNG NGHỆ TOÀN DỰ ÁN (TECH STACK MAP)

Bảng tổng hợp trả lời hội đồng về các công nghệ ứng dụng trong đề tài:

| Tầng Kiến trúc | Công nghệ sử dụng | Mục đích cụ thể |
| :--- | :--- | :--- |
| **Hạ tầng Đám mây (Cloud Infrastructure)** | **Google Colab Pro + Google Drive** | Cung cấp tài nguyên tính toán GPU A100 mạnh mẽ và lưu trữ an toàn 139 GB dữ liệu. |
| **Dữ liệu lớn (Big Data / Storage)** | **Apache Parquet**, **PyArrow** | Lưu trữ dữ liệu dạng cột nén, tối ưu tốc độ đọc/ghi dữ liệu lớn. |
| **Lập chỉ mục & Bộ nhớ (In-memory Index)** | **NumPy (.npy)** | Lưu trữ mảng vector đa phương thức, hỗ trợ tra cứu trực tiếp O(1). |
| **Trí tuệ nhân tạo (Deep Learning)** | **PyTorch (CUDA)** | Khung làm việc (Framework) để xây dựng, huấn luyện và suy luận mô hình MUSE. |
| **Học đa phương thức (Multimodal Learning)**| **SCL (Supervised Contrastive Learning)** | Biểu diễn ảnh và tiêu đề sản phẩm thành vector ngữ nghĩa. |
| **Cơ sở dữ liệu Demo (Serving Database)** | **SQLite / DuckDB** | Lưu trữ và truy vấn nhanh danh mục sản phẩm cho Web Demo từ file `item_features.parquet`. |
| **Giao diện Web (Frontend / App)** | **Streamlit / Gradio** | Xây dựng giao diện web mô phỏng sàn thương mại điện tử trực quan. |
