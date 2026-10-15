# 🛒 Shopee AI - Hệ Thống Gợi Ý Thời Gian Thực Tích Hợp Alibaba MUSE

Dự án Xây dựng Ứng dụng Thương mại Điện tử Đa Nền tảng với Bộ Não Gợi Ý Sản Phẩm Công Nghệ Cao **Alibaba MUSE** (*arXiv:2512.07216*).

## 🚀 Cấu Trúc Dự Án
```text
shopee_muse/
├── checkpoints/       # 2 file trọng số model MUSE (Dense 504KB + Sparse 2.6GB)
├── data/              # Cơ sở dữ liệu SQLite shopee_muse.db (11 bảng, 34 tỉnh thành)
├── app/               # Backend FastAPI (API Router, Database, Recommender AI)
├── templates/         # Giao diện HTML5 Shopee
├── static/            # CSS, JS, Images
├── scripts/           # Script nạp/reset database (init_database.py)
└── requirements.txt   # Thư viện phụ thuộc
```

## 🛠️ Hướng Dẫn Sử Dụng Nhanh
1. **Mở dự án trong Visual Studio Code:**
   ```bash
   code /home/midea/Projects/shopee_muse
   ```
2. **Khởi chạy ứng dụng:**
   ```bash
   cd /home/midea/Projects/shopee_muse
   /home/midea/Projects/demo_env/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
3. **Mở trình duyệt:** Truy cập `http://localhost:8000`
