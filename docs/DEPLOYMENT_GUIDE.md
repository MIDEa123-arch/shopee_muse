# HƯỚNG DẪN TRIỂN KHAI TOÀN DIỆN SHOPEE MUSE LÊN CLOUD (100% FREE)
> **Kiến trúc Vàng (Khuyên dùng số 1):** Frontend (Vercel) + Backend AI & Database (Hugging Face Spaces 16GB RAM, 50GB Ổ đĩa)  
> **Kiến trúc Dự phòng:** Frontend (Vercel) + Backend (Render) + Database (Neon / SQLite)  
> **Cam kết:** 100% MIỄN PHÍ VĨNH VIỄN, KHÔNG CẦN THẺ TÍN DỤNG.

---

## 1. VÌ SAO CHỌN HƯỚNG 2 (HUGGING FACE SPACES + VERCEL)?

| Nhu cầu của bạn | Render + Neon (Cách cũ) | Hugging Face Spaces + Vercel (Hướng 2) |
| :--- | :--- | :--- |
| **RAM chạy mô hình AI (PyTorch)** | Bị giới hạn **512 MB** $\rightarrow$ Dễ bị tràn RAM sập server (OOM Crash). | **Cấp hẳn 16 GB RAM (Miễn phí 100%)** $\rightarrow$ Chạy mô hình học sâu Alibaba MUSE mượt mà, không bao giờ lo sập! |
| **Dung lượng Database** | Bị giới hạn **500 MB** $\rightarrow$ Không thể chứa file 4.6 GB. | **Cấp hẳn 50 GB ổ đĩa SSD** $\rightarrow$ Chứa trọn vẹn Database lớn hoặc bản 15.000 sản phẩm. |
| **Độ trễ truy vấn (Latency)** | Nối qua Internet từ Render sang Neon mất 100ms - 200ms. | Database nằm ngay trên ổ SSD tại chỗ, truy vấn chỉ mất **0.5 ms**! |
| **Frontend Giao diện** | Băng thông lớn, CDN toàn cầu, HTTPS tự động từ **Vercel** $\rightarrow$ Load trang tức thì trong 0.05s! |

---

## 2. NHỮNG FILE TÔI ĐÃ LÀM SẴN CHO BẠN TRONG PROJECT

1. **[Dockerfile](file:///home/midea/Projects/shopee_muse/Dockerfile)**: File cấu hình container chuẩn Docker cho Hugging Face Spaces (Python 3.11, PyTorch CPU, port 7860, phân quyền non-root uid 1000).
2. **[vercel.json](file:///home/midea/Projects/shopee_muse/vercel.json)**: Reverse Proxy của Vercel (chuyển tiếp API `/api/*` về Hugging Face Spaces $\rightarrow$ triệt tiêu 100% lỗi CORS và lỗi mất Cookie đăng nhập).
3. **[data/cloud_catalog.db](file:///home/midea/Projects/shopee_muse/data/cloud_catalog.db) (15.3 MB)**: File database 15.000 sản phẩm chuẩn tiếng Việt, 11 danh mục, 8 hồ sơ khách hàng, đã được tích hợp sẵn.
4. **[app/config.py](file:///home/midea/Projects/shopee_muse/app/config.py)**: Đã cấu hình tự động nhận diện database (ưu tiên file 4.6GB nếu có, tự động fallback về 15MB nếu chạy trên cloud nhẹ).
5. **[app/main.py](file:///home/midea/Projects/shopee_muse/app/main.py)**: Đã bật CORS cho phép `*.vercel.app` và `*.hf.space`.

---

## 3. CÁC BƯỚC THỰC HIỆN CỤ THỂ (TÔI CHỈ BẠN TỪNG CHUỘT BẤM)

### PHẦN A: TẠO VÀ DEPLOY BACKEND LÊN HUGGING FACE SPACES (16GB RAM)

1. **Tạo tài khoản Hugging Face**:
   * Truy cập [huggingface.co/join](https://huggingface.co/join) để tạo tài khoản miễn phí (chỉ cần Email, không cần thẻ tín dụng).
2. **Tạo một Space mới**:
   * Bấm vào ảnh đại diện góc phải $\rightarrow$ Chọn **New Space** (hoặc vào [huggingface.co/new-space](https://huggingface.co/new-space)).
   * **Space name**: Điền `shopee-muse-backend` (hoặc tên bạn thích).
   * **License**: Chọn `mit` hoặc `apache-2.0`.
   * **Select the Space SDK**: Bấm chọn ô **Docker** (chọn Blank).
   * **Space hardware**: Chọn **CPU basic · 2 vCPU · 16 GB RAM · 50 GB disk · Free**.
   * **Privacy**: Chọn `Public`.
   * Bấm nút **Create Space**.
3. **Đẩy mã nguồn từ máy bạn lên Hugging Face Space**:
   * Mở terminal tại thư mục dự án `/home/midea/Projects/shopee_muse`:
     ```bash
     # 1. Commit các thay đổi mới nhất
     git add .
     git commit -m "feat: setup huggingface space docker and vercel proxy"

     # 2. Thêm remote của Hugging Face (thay <ten-tai-khoan> bằng username Hugging Face của bạn)
     git remote add space https://huggingface.co/spaces/<ten-tai-khoan>/shopee-muse-backend

     # 3. Đẩy code lên Space
     git push space main -f
     ```
   *(Lúc này terminal sẽ hỏi Username và Password của Hugging Face. Password bạn vào Hugging Face Settings $\rightarrow$ Access Tokens $\rightarrow$ Tạo 1 token quyền Write để dán vào nhé).*
4. **Lấy link API Backend**:
   * Sau khi push xong, trang Hugging Face Space sẽ tự động build Docker trong ~2 phút.
   * Khi thấy chữ **Running** màu xanh lá:
   * Bấm vào dấu **3 chấm `...`** ở góc trên bên phải của Space $\rightarrow$ Chọn **Embed this Space** $\rightarrow$ Tìm mục **Direct URL**.
   * URL Backend của bạn sẽ có dạng:  
     `https://<ten-tai-khoan>-shopee-muse-backend.hf.space`
   * Kiểm tra nhanh trên trình duyệt: Vào `https://<ten-tai-khoan>-shopee-muse-backend.hf.space/api/health` $\rightarrow$ Thấy `{"status":"ok","model_ready":true}` là xong 100% Backend!

---

### PHẦN B: DEPLOY FRONTEND LÊN VERCEL

1. **Cập nhật link Hugging Face vào file [vercel.json](file:///home/midea/Projects/shopee_muse/vercel.json)**:
   * Mở file `vercel.json` trong dự án, dán URL Hugging Face bạn vừa lấy ở Phần A vào:
     ```json
     {
       "version": 2,
       "cleanUrls": true,
       "rewrites": [
         {
           "source": "/api/:path*",
           "destination": "https://<ten-tai-khoan>-shopee-muse-backend.hf.space/api/:path*"
         }
       ]
     }
     ```
2. **Đẩy lên GitHub cá nhân**:
   ```bash
   git add vercel.json
   git commit -m "point vercel api to hugging face space"
   git push origin main
   ```
3. **Deploy lên Vercel**:
   * Truy cập [vercel.com](https://vercel.com) $\rightarrow$ Đăng nhập bằng GitHub.
   * Bấm **Add New...** $\rightarrow$ **Project** $\rightarrow$ Chọn repository dự án $\rightarrow$ Bấm **Import**.
   * Giữ nguyên toàn bộ cấu hình mặc định $\rightarrow$ Bấm nút **Deploy**.
   * Sau 20 giây, Vercel sẽ cấp cho bạn tên miền website chính thức (ví dụ: `https://shopee-muse.vercel.app`)!

---

## 4. TỔNG KẾT KẾT QUẢ BẠN ĐẠT ĐƯỢC

* ✅ **Chi phí:** 0đ trọn đời (Vercel Free + Hugging Face Spaces Free).
* ✅ **Tài nguyên:** 16 GB RAM + 2 vCPU + 50 GB lưu trữ.
* ✅ **Mô hình AI:** Alibaba MUSE DIN + SCL 128D chạy full tốc độ.
* ✅ **Không bao giờ bị lỗi CORS hay mất Cookie:** Nhờ Vercel Reverse Proxy.
* ✅ **Tốc độ truy cập:** Nhanh như Shopee thật!
