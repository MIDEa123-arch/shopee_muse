import sqlite3
import json
import random
import os
import hashlib
import pyarrow.parquet as pq

DB_PATH = "/home/midea/Projects/shopee_muse/shopee_muse.db"
TEST_SHARD = "/home/midea/TaoBao_dataset/test/test-shard-000000.parquet"
ITEM_FEATURES = "/home/midea/TaoBao_dataset/raw/item_features.parquet"

print("🚀 Đang cập nhật Cơ sở Dữ liệu Shopee - Alibaba MUSE (Phiên bản Chuẩn hóa Toàn diện)...")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. TẠO CÁC BẢNG DỮ LIỆU
cursor.executescript("""
DROP TABLE IF EXISTS recommendation_logs;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS cart_items;
DROP TABLE IF EXISTS user_vouchers;
DROP TABLE IF EXISTS vouchers;
DROP TABLE IF EXISTS user_behavior_history;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS provinces;

CREATE TABLE provinces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'Thành phố trực thuộc TW' hoặc 'Tỉnh'
    region TEXT NOT NULL,
    shipping_base_fee INTEGER DEFAULT 22000
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    icon TEXT
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_user_id INTEGER UNIQUE,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    avatar_url TEXT,
    gender TEXT,
    birth_year INTEGER,
    province_id INTEGER,
    address_detail TEXT,
    member_tier TEXT DEFAULT 'Vàng',
    shopee_coins INTEGER DEFAULT 50000,
    wallet_balance INTEGER DEFAULT 1500000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (province_id) REFERENCES provinces(id)
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_item_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    category_id INTEGER,
    price INTEGER NOT NULL,
    original_price INTEGER NOT NULL,
    discount_percent INTEGER NOT NULL,
    stock INTEGER DEFAULT 100,
    sold_count INTEGER DEFAULT 0,
    rating_star REAL DEFAULT 4.9,
    rating_count INTEGER DEFAULT 0,
    image_url TEXT NOT NULL,
    province_id INTEGER,
    shop_name TEXT NOT NULL,
    is_mall BOOLEAN DEFAULT 1,
    is_freeship BOOLEAN DEFAULT 1,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (province_id) REFERENCES provinces(id)
);

CREATE TABLE user_behavior_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    raw_user_id INTEGER NOT NULL,
    product_id INTEGER,
    raw_item_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE vouchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    discount_type TEXT NOT NULL,
    discount_value INTEGER NOT NULL,
    min_order_value INTEGER DEFAULT 0,
    max_discount_amount INTEGER,
    end_date TEXT DEFAULT '2026-12-31'
);

CREATE TABLE user_vouchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    voucher_id INTEGER NOT NULL,
    status TEXT DEFAULT 'available',
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (voucher_id) REFERENCES vouchers(id)
);

CREATE TABLE cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER DEFAULT 1,
    is_selected BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_code TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    total_goods_amount INTEGER NOT NULL,
    shipping_fee INTEGER NOT NULL,
    voucher_discount INTEGER DEFAULT 0,
    coin_discount INTEGER DEFAULT 0,
    final_payment_amount INTEGER NOT NULL,
    payment_method TEXT DEFAULT 'ShopeePay',
    order_status TEXT DEFAULT 'Chờ xác nhận',
    recipient_name TEXT NOT NULL,
    recipient_phone TEXT NOT NULL,
    shipping_address TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    type TEXT DEFAULT 'recommendation',
    is_read BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE recommendation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    touchpoint TEXT NOT NULL,
    candidate_count INTEGER,
    top_recommended_ids TEXT,
    model_name TEXT DEFAULT 'Alibaba_MUSE',
    latency_ms REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
""")

print("✅ Đã tạo cấu trúc 11 bảng cơ sở dữ liệu.")

# 2. CHÈN 34 ĐƠN VỊ HÀNH CHÍNH CẤP TỈNH MỚI NHẤT (6 THÀNH PHỐ TRỰC THUỘC TW + 28 TỈNH)
VN_ADMIN_UNITS = [
    # 6 Thành phố trực thuộc Trung ương
    ("Thành phố Hà Nội", "Thành phố trực thuộc TW", "Miền Bắc", 20000),
    ("Thành phố Hồ Chí Minh", "Thành phố trực thuộc TW", "Miền Nam", 20000),
    ("Thành phố Hải Phòng", "Thành phố trực thuộc TW", "Miền Bắc", 22000),
    ("Thành phố Đà Nẵng", "Thành phố trực thuộc TW", "Miền Trung", 22000),
    ("Thành phố Huế", "Thành phố trực thuộc TW", "Miền Trung", 24000),
    ("Thành phố Cần Thơ", "Thành phố trực thuộc TW", "Miền Nam", 24000),
    
    # 28 Tỉnh theo mô hình tổ chức hành chính tinh gọn mới
    ("An Giang", "Tỉnh", "Miền Nam", 28000),
    ("Bắc Ninh", "Tỉnh", "Miền Bắc", 22000),
    ("Cà Mau", "Tỉnh", "Miền Nam", 30000),
    ("Cao Bằng", "Tỉnh", "Miền Bắc", 30000),
    ("Đắk Lắk", "Tỉnh", "Miền Trung", 28000),
    ("Điện Biên", "Tỉnh", "Miền Bắc", 30000),
    ("Đồng Nai", "Tỉnh", "Miền Nam", 22000),
    ("Đồng Tháp", "Tỉnh", "Miền Nam", 26000),
    ("Gia Lai", "Tỉnh", "Miền Trung", 28000),
    ("Hà Tĩnh", "Tỉnh", "Miền Trung", 25000),
    ("Khánh Hòa", "Tỉnh", "Miền Trung", 25000),
    ("Lai Châu", "Tỉnh", "Miền Bắc", 32000),
    ("Lâm Đồng", "Tỉnh", "Miền Trung", 26000),
    ("Lạng Sơn", "Tỉnh", "Miền Bắc", 28000),
    ("Lào Cai", "Tỉnh", "Miền Bắc", 28000),
    ("Nghệ An", "Tỉnh", "Miền Trung", 25000),
    ("Ninh Bình", "Tỉnh", "Miền Bắc", 22000),
    ("Phú Thọ", "Tỉnh", "Miền Bắc", 24000),
    ("Quảng Ngãi", "Tỉnh", "Miền Trung", 26000),
    ("Quảng Ninh", "Tỉnh", "Miền Bắc", 24000),
    ("Quảng Trị", "Tỉnh", "Miền Trung", 26000),
    ("Sơn La", "Tỉnh", "Miền Bắc", 30000),
    ("Tây Ninh", "Tỉnh", "Miền Nam", 25000),
    ("Thái Nguyên", "Tỉnh", "Miền Bắc", 24000),
    ("Thanh Hóa", "Tỉnh", "Miền Trung", 24000),
    ("Tuyên Quang", "Tỉnh", "Miền Bắc", 28000),
    ("Vĩnh Long", "Tỉnh", "Miền Nam", 26000),
    ("Bình Dương", "Tỉnh", "Miền Nam", 22000)
]

for unit in VN_ADMIN_UNITS:
    cursor.execute("INSERT INTO provinces (name, type, region, shipping_base_fee) VALUES (?, ?, ?, ?)", unit)
print(f"✅ Đã nạp chính xác {len(VN_ADMIN_UNITS)} Đơn vị hành chính cấp tỉnh mới nhất (6 TP TW + 28 Tỉnh).")

# 3. CHÈN DANH MỤC SẢN PHẨM
CATEGORIES = [
    ("Thiết Bị Điện Tử & Công Nghệ", "dien-tu", "fa-laptop"),
    ("Âm Thanh & Tai Nghe", "am-thanh", "fa-headphones"),
    ("Thời Trang Nam", "thoi-trang-nam", "fa-tshirt"),
    ("Thời Trang Nữ", "thoi-trang-nu", "fa-female"),
    ("Giày Dép & Sneaker", "giay-dep", "fa-shoe-prints"),
    ("Đồ Gia Dụng Thông Minh", "gia-dung", "fa-blender"),
    ("Mỹ Phẩm & Sắc Đẹp", "my-pham", "fa-spa"),
    ("Đồng Hồ & Phụ Kiện", "phu-kien", "fa-clock")
]
for cat in CATEGORIES:
    cursor.execute("INSERT INTO categories (name, slug, icon) VALUES (?, ?, ?)", cat)
print(f"✅ Đã nạp {len(CATEGORIES)} danh mục ngành hàng.")

# 4. CHÈN VOUCHERS KHUYẾN MÃI
VOUCHERS = [
    ("FREESHIP50K", "Miễn Phí Vận Chuyển Toàn Quốc", "Giảm 50.000đ phí vận chuyển cho đơn từ 150.000đ", "freeship", 50000, 150000, 50000),
    ("SHOPEEAI20", "Ưu Đãi Công Nghệ AI MUSE", "Giảm ngay 20% cho các sản phẩm gợi ý thông minh", "percentage", 20, 200000, 100000),
    ("VOUCHERMUSE30K", "Voucher Thành Viên Mới", "Giảm thẳng 30.000đ cho đơn hàng đầu tiên", "fixed_amount", 30000, 100000, 30000),
    ("MUSEVIP100K", "Đặc Quyền Thành Viên Vàng", "Giảm 100.000đ cho đơn từ 500.000đ", "fixed_amount", 100000, 500000, 100000)
]
for v in VOUCHERS:
    cursor.execute("INSERT INTO vouchers (code, title, description, discount_type, discount_value, min_order_value, max_discount_amount) VALUES (?, ?, ?, ?, ?, ?, ?)", v)
print(f"✅ Đã nạp {len(VOUCHERS)} mã giảm giá.")

# 5. TRÍCH XUẤT 1,000 SẢN PHẨM THẬT TỪ TAOBAO VÀ GÁN DỮ LIỆU TIẾNG VIỆT
print("⏳ Đang trích xuất 1,000 sản phẩm thật từ item_features.parquet...")
pf_item = pq.ParquetFile(ITEM_FEATURES)
table_item = next(pf_item.iter_batches(batch_size=1000)).to_pandas()

PRODUCT_TEMPLATES = {
    1: [
        ("Bàn Phím Cơ Không Dây Gaming RGB 3 Chế Độ Kết Nối", 650000, 850000, "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&q=80"),
        ("Chuột Không Dây Gaming Cảm Biến Quang Học 16000 DPI", 390000, 550000, "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=500&q=80"),
        ("Cáp Sạc Nhanh Type-C to Lightning Chuẩn PD 20W Bọc Dù", 89000, 150000, "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=500&q=80"),
        ("Đế Tản Nhiệt Laptop Nhôm Nguyên Khối 6 Cấp Độ Nghiêng", 220000, 320000, "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80"),
        ("Màn Hình Gaming 24 inch 144Hz IPS Viền Siêu Mỏng", 2490000, 3500000, "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80")
    ],
    2: [
        ("Tai Nghe Bluetooth True Wireless Chống Ồn ANC Pin 30 Giờ", 480000, 750000, "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80"),
        ("Loa Bluetooth Mini Cầm Tay Chống Nước IPX7 Bass Cực Căng", 320000, 490000, "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=500&q=80"),
        ("Tai Nghe Chụp Tai Gaming Headphone Âm Thanh Vòm 7.1", 590000, 890000, "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=500&q=80"),
        ("Micro Thu Âm Cài Áo Không Dây Thu Âm Lọc Ồn Chuyên Nghiệp", 299000, 450000, "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80")
    ],
    3: [
        ("Áo Thun Nam Cổ Tròn Cotton 100% Co Giãn 4 Chiều Form Rộng", 139000, 199000, "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500&q=80"),
        ("Áo Khoác Gió Thể Thao Nam Chống Thấm Nước 2 Lớp Cao Cấp", 280000, 420000, "https://images.unsplash.com/photo-1544441893-675973e31985?w=500&q=80"),
        ("Quần Jogger Nam Vải Nỉ Thể Thao Dáng Ôm Năng Động", 195000, 290000, "https://images.unsplash.com/photo-1552902865-b72c031ac5ea?w=500&q=80"),
        ("Áo Sơ Mi Nam Công Sở Dài Tay Chống Nhăn Cao Cấp", 249000, 380000, "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=500&q=80")
    ],
    4: [
        ("Váy Đầm Nữ Dáng Dài Cổ Vuông Tiểu Thư Dạo Phố Dự Tiệc", 299000, 450000, "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=500&q=80"),
        ("Áo Sơ Mi Nữ Tay Phồng Phong Cách Hàn Quốc Thanh Lịch", 185000, 260000, "https://images.unsplash.com/photo-1598554747436-c9293d6a588f?w=500&q=80"),
        ("Chân Váy Chữ A Xếp Ly Lưng Cao Tôn Dáng Thời Trang", 145000, 220000, "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=500&q=80"),
        ("Set Bộ Đồ Nữ Thể Thao Năng Động Dạo Phố Mùa Hè", 230000, 350000, "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500&q=80")
    ],
    5: [
        ("Giày Thể Thao Sneaker Nam Cổ Thấp Đế Đệm Êm Ái Đi Học Đi Chơi", 389000, 590000, "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&q=80"),
        ("Giày Sneaker Nữ Phong Cách Hàn Quốc Đế Cao Hack Dáng", 320000, 480000, "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=500&q=80"),
        ("Dép Quai Ngang Đúc Nguyên Khối Chống Trơn Trượt", 89000, 130000, "https://images.unsplash.com/photo-1603808033192-082d6919d3e1?w=500&q=80"),
        ("Giày Lười Nam Da Bò Thật Kháng Khuẩn Đế Cao Su Đúc", 520000, 850000, "https://images.unsplash.com/photo-1533867617858-e7b97e060509?w=500&q=80")
    ],
    6: [
        ("Nồi Chiên Không Dầu Điện Tử 6.5L Lòng Nồi Chống Dính Cao Cấp", 890000, 1450000, "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=500&q=80"),
        ("Máy Pha Cà Phê Mini Espresso Tự Động Tạo Bọt Sữa", 1250000, 1890000, "https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=500&q=80"),
        ("Robot Hút Bụi Lau Nhà Thông Minh Điều Khiển Qua App", 2490000, 3800000, "https://images.unsplash.com/photo-1518640467707-6811f4a6ab73?w=500&q=80"),
        ("Máy Xay Sinh Tố Cầm Tay Đa Năng 6 Lưỡi Dao Inox 304", 210000, 350000, "https://images.unsplash.com/photo-1570222094114-d054a817e56b?w=500&q=80")
    ],
    7: [
        ("Serum Dưỡng Ẩm Phục Hồi Da Hyaluronic B5 Căng Bóng Mịn Màng", 245000, 360000, "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=500&q=80"),
        ("Kem Chống Nắng Phổ Rộng Nâng Tông Kiềm Dầu SPF50+ PA++++", 195000, 290000, "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=500&q=80"),
        ("Son Kem Lì Mịn Môi Lâu Trôi Màu Đỏ Đất Thời Thượng", 165000, 250000, "https://images.unsplash.com/photo-1586495777744-4413f21062fa?w=500&q=80"),
        ("Nước Tẩy Trang Làm Sạch Sâu Dịu Nhẹ Cho Da Nhạy Cảm 500ml", 145000, 220000, "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=500&q=80")
    ],
    8: [
        ("Đồng Hồ Nam Dây Da Cao Cấp Chống Nước Mặt Kính Sapphire", 690000, 1200000, "https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=500&q=80"),
        ("Kính Mát Thời Trang Unisex Chống Tia UV400 Gọng Kim Loại", 180000, 290000, "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=500&q=80"),
        ("Ví Nam Da Bò Mini Đứng Nhỏ Gọn Nhiều Ngăn Đựng Thẻ", 160000, 260000, "https://images.unsplash.com/photo-1627123424574-724758594e93?w=500&q=80")
    ]
}

SHOPS = [
    ("Anker Official Store", 1), ("Sony Mall Vietnam", 2), ("Coolmate Official", 1),
    ("Yame Fashion Store", 2), ("Biti's Hunter Flagship", 2), ("Philips Home Appliances", 1),
    ("L'Oréal Paris Mall", 2), ("Casio Vietnam Store", 1)
]

inserted_items = 0
for idx, row in table_item.iterrows():
    raw_id = int(row['205'])
    cat_id = (idx % len(CATEGORIES)) + 1
    templates = PRODUCT_TEMPLATES[cat_id]
    tpl = templates[idx % len(templates)]
    
    variant = (idx // len(templates)) + 1
    name = f"{tpl[0]} (Model #{variant})"
    price = tpl[1] + (variant * 5000) % 30000
    orig_price = tpl[2] + (variant * 5000) % 30000
    discount = int((orig_price - price) / orig_price * 100)
    img_url = tpl[3]
    
    shop = SHOPS[cat_id - 1]
    shop_name = shop[0]
    prov_id = shop[1]
    
    sold = random.randint(150, 6500)
    rating = round(random.uniform(4.7, 5.0), 1)
    rev_count = int(sold * random.uniform(0.3, 0.6))
    
    cursor.execute("""
    INSERT OR IGNORE INTO products 
    (raw_item_id, name, category_id, price, original_price, discount_percent, stock, sold_count, rating_star, rating_count, image_url, province_id, shop_name)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (raw_id, name, cat_id, price, orig_price, discount, random.randint(50, 300), sold, rating, rev_count, img_url, prov_id, shop_name))
    inserted_items += 1

print(f"✅ Đã nạp thành công {inserted_items} sản phẩm từ Taobao-MM vào kho hàng.")

# 6. HASH MẬT KHẨU BẢO MẬT BẰNG SHA-256
def hash_password(password: str) -> str:
    # Chuẩn bảo mật lưu trữ: Mã hóa 1 chiều SHA-256
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

DEFAULT_PASSWORD_HASH = hash_password("123456")

# 7. TRÍCH XUẤT NGƯỜI DÙNG THẬT TỪ TEST SHARD KÈM LỊCH SỬ 1K HÀNH VI
print("⏳ Đang trích xuất người dùng thật từ test-shard-000000.parquet...")
pf_test = pq.ParquetFile(TEST_SHARD)
test_batch = next(pf_test.iter_batches(batch_size=100)).to_pandas()

SAMPLE_PROFILES = [
    ("Nguyễn Văn Nam", "nam.nguyen@gmail.com", "0912345678", "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150", "Nam", 2001, 1, "Số 12 Chùa Bộc, Đống Đa, Hà Nội", "Kim Cương", 85000, 2500000),
    ("Trần Thị Mai Lan", "lan.tran@gmail.com", "0987654321", "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150", "Nữ", 1998, 2, "142 Nguyễn Thị Minh Khai, Quận 3, TP.HCM", "Vàng", 45000, 1200000),
    ("Lê Hoàng Anh", "anh.le@gmail.com", "0905123456", "https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?w=150", "Nam", 1995, 4, "88 Nguyễn Văn Linh, Hải Châu, Đà Nẵng", "Bạc", 20000, 850000),
    ("Phạm Minh Tuấn (Gia Đình)", "tuan.pham@gmail.com", "0918889999", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150", "Nam", 1989, 2, "Vinhomes Central Park, Bình Thạnh, TP.HCM", "Kim Cương", 150000, 5000000),
    ("Đặng Thu Thảo", "thao.dang@gmail.com", "0934567890", "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150", "Nữ", 2003, 1, "Ký Túc Xá ĐHQG, Cầu Giấy, Hà Nội", "Thành viên Mới", 10000, 300000),
    ("Vũ Hoàng Nam", "hoangnam.vu@gmail.com", "0971122334", "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150", "Nam", 1997, 3, "25 Lạch Tray, Ngô Quyền, Hải Phòng", "Vàng", 60000, 1800000),
    ("Hoàng Thị Hương", "huong.hoang@gmail.com", "0989988776", "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150", "Nữ", 1993, 5, "12 Lê Lợi, TP. Huế", "Bạc", 35000, 950000),
    ("Ngô Quốc Bảo", "bao.ngo@gmail.com", "0909112233", "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150", "Nam", 2000, 6, "30 Tháng 4, Ninh Kiều, Cần Thơ", "Vàng", 50000, 1400000)
]

unique_users_seen = set()
user_idx = 0

for _, row in test_batch.iterrows():
    raw_uid = int(row['129_1'])
    if raw_uid in unique_users_seen:
        continue
    unique_users_seen.add(raw_uid)
    
    prof = SAMPLE_PROFILES[user_idx % len(SAMPLE_PROFILES)]
    name = f"{prof[0]} (#{user_idx+1})"
    email = f"user_{user_idx+1}_{prof[1]}"
    phone = prof[2]
    avatar = prof[3]
    gender = prof[4]
    byear = prof[5]
    prov_id = prof[6]
    addr = prof[7]
    tier = prof[8]
    coins = prof[9]
    wallet = prof[10]
    
    cursor.execute("""
    INSERT OR IGNORE INTO users 
    (raw_user_id, full_name, email, phone, password_hash, avatar_url, gender, birth_year, province_id, address_detail, member_tier, shopee_coins, wallet_balance)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (raw_uid, name, email, phone, DEFAULT_PASSWORD_HASH, avatar, gender, byear, prov_id, addr, tier, coins, wallet))
    
    uid = cursor.lastrowid
    
    # Nạp chuỗi lịch sử thật của user (lấy 40 món gần nhất từ tập Test)
    seq = row['150_2_180']
    if hasattr(seq, '__iter__'):
        history_items = list(seq)[:40]
        for raw_item in history_items:
            cursor.execute("""
            INSERT INTO user_behavior_history (user_id, raw_user_id, raw_item_id, action_type)
            VALUES (?, ?, ?, 'click')
            """, (uid, raw_uid, int(raw_item)))
            
    # Tặng voucher cho user
    cursor.execute("INSERT INTO user_vouchers (user_id, voucher_id) VALUES (?, 1)", (uid,))
    cursor.execute("INSERT INTO user_vouchers (user_id, voucher_id) VALUES (?, 2)", (uid,))
    
    # Tạo thông báo chào mừng
    cursor.execute("""
    INSERT INTO notifications (user_id, title, content, type)
    VALUES (?, 'Chào mừng bạn đến với Shopee AI!', 'Hệ thống AI MUSE đã nạp sẵn sở thích mua sắm của bạn. Khám phá ngay các ưu đãi hôm nay!', 'system')
    """, (uid,))
    
    user_idx += 1
    if user_idx >= 8:
        break

print(f"✅ Đã nạp {user_idx} người dùng mẫu với MẬT KHẨU ĐÃ ĐƯỢC MÃ HÓA SHA-256 ({DEFAULT_PASSWORD_HASH[:10]}...).")

conn.commit()
conn.close()

print(f"\n🎉 HOÀN TẤT KHỞI TẠO CƠ SỞ DỮ LIỆU: {DB_PATH}")
print(f"Kích thước file DB: {os.path.getsize(DB_PATH) / 1024:.2f} KB")
