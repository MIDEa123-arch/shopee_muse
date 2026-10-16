"""Populate all items from the 8 demo users' behavior sequences into the product catalog.
Maps 100% of user_behavior_history (1,000 items per user) to real, distinct products with
genuine Vietnamese names, photos, prices, categories, and shops.
Eliminates all 'Sản phẩm Taobao ngoài danh mục demo'!
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config

# Curated vocabulary per category to generate 1,000+ completely unique realistic Vietnamese titles
VOCAB = {
    1: {  # Điện tử & Công nghệ
        'brands': ['ASUS', 'Lenovo', 'Dell', 'HP', 'Apple', 'Acer', 'MSI', 'Logitech', 'Keychron', 'Anker',
                   'Baseus', 'Ugreen', 'Samsung', 'Sandisk', 'Kingston', 'DareU', 'Akko', 'Razer', 'Corsair',
                   'Edifier', 'BenQ', 'LG', 'ViewSonic', 'Microsoft', 'HyperX', 'Belkin', 'Orico', 'TP-Link'],
        'types': ['Laptop Gaming', 'Bàn Phím Cơ', 'Chuột Không Dây', 'Màn Hình Đồ Họa IPS', 'Ổ Cứng Di Động SSD',
                  'Củ Sạc Nhanh GaN', 'Hub Chuyển Đổi Type-C', 'Tai Nghe Gaming Chụp Tai', 'Webcam Full HD 1080p',
                  'Bút Cảm Ứng Stylus', 'Giá Đỡ Hợp Kim Nhôm Laptop', 'Bàn Di Chuột Cỡ Lớn', 'Thẻ Nhớ MicroSD 4K',
                  'Pin Sạc Dự Phòng Sạc Nhanh', 'Router WiFi 6 Băng Tần Kép', 'Kê Tay Công Thái Học Bàn Phím',
                  'Cáp Sạc C to C 100W', 'Đèn Treo Màn Hình Chống Chói', 'Hộp Đựng Phụ Kiện Chống Sốc', 'Quạt Tản Nhiệt Sò Lạnh'],
        'specs': ['144Hz 1ms Fast IPS', '65W GaN Siêu Nhỏ Gọn', 'Hot-swap RGB 3 Chế Độ', 'Bluetooth 5.3 Không Dây',
                  '1TB NVMe PCIe 4.0 Tốc Độ Cao', 'Chuẩn Sạc Nhanh PD 100W', 'Vỏ Hợp Kim Nhôm CNC Nguyên Khối',
                  'Chống Ồn Kép ENC Đàm Thoại', 'Độ Phân Giải 2K QHD Sắc Nét', 'Gasket Mount Tiêu Âm Êm Ái',
                  'Siêu Nhẹ 59g Cảm Biến HERO', '8 Cổng Đa Năng 4K 60Hz', 'Silent Switch Chống Ồn Văn Phòng',
                  'Chống Nước Chuẩn IPX5', 'Dung Lượng 20000mAh 65W', 'Bọc Vải Dù Siêu Bền Chống Gãy',
                  'Cảm Ứng Chạm Vô Cấp', 'Thiết Kế Đứng Ergonomic', 'Tốc Độ Đọc 1050MB/s', 'Đèn Nền RGB 16.8 Triệu Màu'],
        'shops': ['ASUS Official Store', 'Lenovo Flagship', 'Logitech G Mall', 'Anker Official', 'Ugreen Vietnam', 'Keychron Official', 'Dell Authorized Store']
    },
    2: {  # Âm thanh & Tai nghe
        'brands': ['Sony', 'JBL', 'Marshall', 'Bose', 'Sennheiser', 'Audio-Technica', 'Edifier', 'Soundcore',
                   'Beats', 'Shure', 'Jabra', 'Bang & Olufsen', 'Harman Kardon', 'FiiO', 'Moondrop', 'KZ Audio'],
        'types': ['Tai Nghe Chống Ồn Chủ Động ANC', 'Tai Nghe True Wireless TWS', 'Loa Bluetooth Di Động',
                  'Loa Soundbar Tivi & Phòng Khách', 'Tai Nghe Kiểm Âm Studio', 'Micro Thu Âm Livestream',
                  'Tai Nghe Thể Thao Chống Nước', 'Loa Vi Tính Để Bàn 2.0', 'Dac Amp Giải Mã Âm Thanh Hi-Res',
                  'Tai Nghe Chụp Tai Vintage', 'Loa Cầm Tay Mini Bass Sâu', 'Micro Không Dây Cài Áo Chống Ồn'],
        'specs': ['Chuẩn Hi-Res LDAC Âm Thanh Vòm', 'Pin Khủng 50 Giờ Sạc Nhanh', 'Chống Bụi Nước IP67 Đi Biển',
                  'Driver Dynamic 40mm Màng Titan', 'Khử 98.5% Tiếng Ồn Thích Ứng', 'Công Suất 40W Bass Cực Căng',
                  'Đệm Tai Da Protein Êm Ái', 'Độ Trễ Siêu Thấp 40ms Gaming', 'Tích Hợp 4 Mic Đàm Thoại AI',
                  'Kết Nối Đa Điểm 2 Thiết Bị', 'Thiết Kế Da Cổ Điển Sang Trọng', 'Kháng Mồ Hôi IPX7 Tập Gym'],
        'shops': ['Sony Mall Vietnam', 'JBL Official Store', 'Marshall Flagship', 'Bose Vietnam', 'Soundcore Official', 'Edifier Vietnam', 'FiiO Audio Store']
    },
    3: {  # Thời trang nam
        'brands': ['Coolmate', 'Routine', 'Biluxury', 'SSStutter', 'Davies', 'Dirty Coins', 'Levents', 'Aristino',
                   'Owen', 'Viettien', 'Degrey', 'Hades', '5S Fashion', 'Yame', 'Torano', 'Novelty'],
        'types': ['Áo Polo Nam', 'Áo Thun Nam Cổ Tròn', 'Áo Sơ Mi Nam Công Sở Dài Tay', 'Quần Tây Nam Slimfit',
                  'Quần Jean Nam Ống Suông', 'Áo Khoác Gió Thể Thao Nam 2 Lớp', 'Áo Hoodie Nam Nỉ Bông',
                  'Quần Jogger Nam Thể Thao', 'Quần Short Kaki Nam', 'Áo Khoác Bomber Nam',
                  'Áo Sơ Mi Nam Vải Đũi Cổ Tàu', 'Áo Khoác Jean Nam Denim', 'Quần Kaki Chinos Nam', 'Áo Thun Ba Lỗ Nam Gym'],
        'specs': ['Vải Cotton Compact 100% Co Giãn 4 Chiều', 'Chất Vải Pique Sợi Cafe Khử Mùi', 'Chống Nhăn Easy Iron Thoáng Mát',
                  'Phom Regular Thanh Lịch Tôn Dáng', 'Vải Nỉ Da Cá Dày Dặn Giữ Ấm', 'Kháng Nước Chống Gió Có Mũ',
                  'Wash Xước Bụi Bặm Streetwear', 'Lưng Thun Dây Rút Co Giãn Thoải Mái', 'Cổ Bẻ Dệt Bo Viền Tinh Tế',
                  'Dệt Tổ Ong Waffle Thoáng Khí', 'In Graphic Trẻ Trung Unisex', 'Sợi Tre Bamboo Kháng Khuẩn Tự Nhiên'],
        'shops': ['Coolmate Official', 'Routine Flagship', 'Biluxury Store', 'SSStutter Official', 'Davies Streetwear', 'Aristino Mall', 'Dirty Coins Store']
    },
    4: {  # Thời trang nữ
        'brands': ['Marc Fashion', 'Elise', 'Ivy Moda', 'Gumac', 'Dottie', 'Chic-Land', 'Hítt', 'Charme',
                   'Juno', 'Mia', 'Lemino', 'NEM Fashion', 'Sixdo', 'Vascara', 'Khaisilk'],
        'types': ['Váy Đầm Dáng Dài Tiểu Thư', 'Đầm Maxi Đi Biển Voan Hoa', 'Áo Sơ Mi Nữ Tay Phồng', 'Áo Blazer Nữ 2 Lớp',
                  'Chân Váy Chữ A Xếp Ly', 'Quần Tây Nữ Ống Rộng Cạp Cao', 'Áo Kiểu Nữ Cổ Vuông Tay Bồng', 'Đầm Suông Chữ A',
                  'Áo Khoác Dạ Tweed Sang Trọng', 'Set Bộ Váy Công Sở Trẻ Trung', 'Chân Váy Jean Xẻ Tà Dáng Dài',
                  'Áo Thun Nữ Croptop Ôm Body', 'Đầm Dự Tiệc Bodycon Quyến Rũ', 'Áo Cardigan Len Dệt Kim'],
        'specs': ['Chất Voan Tơ Bồng Bềnh 2 Lớp', 'Lưng Cao Hack Dáng Che Khuyết Điểm', 'Cúc Ngọc Trai Đính Tinh Xảo',
                  'Vải Tuyết Mưa Dày Dặn Đứng Phom', 'Độn Vai Tự Nhiên Chuẩn Hàn Quốc', 'Dập Ly Xếp Tầng Điệu Đà',
                  'Chiết Eo Tôn Dáng Duyên Dáng', 'Vải Linen Tự Nhiên Thoáng Nhẹ', 'Họa Tiết Hoa Nhí Ngọt Ngào',
                  'Cổ Vuông Khoe Xương Quai Xanh', 'Chất Lụa Satin Rủ Mềm Mại', 'Co Giãn 4 Chiều Thoải Mái Cả Ngày'],
        'shops': ['Marc Fashion Official', 'Elise Flagship', 'Gumac Official', 'Ivy Moda Store', 'Dottie Studio', 'NEM Fashion Mall', 'Sixdo Official']
    },
    5: {  # Giày dép & Sneaker
        'brands': ['Biti\'s Hunter', 'Nike', 'Adidas', 'Converse', 'Vans', 'Puma', 'New Balance', 'MLB Korea',
                   'Rieker', 'Clarks', 'Skechers', 'Onitsuka Tiger', 'Asics', 'Fila', 'Crocs'],
        'types': ['Giày Sneaker Thể Thao Nam Nữ', 'Giày Chạy Bộ Siêu Nhẹ', 'Giày Lười Nam Penny Loafer Da Thật',
                  'Giày Cao Gót Nữ Mũi Nhọn 7cm', 'Giày Sandal Quai Dù Đi Mưa', 'Dép Quai Ngang Đúc Nguyên Khối EVA',
                  'Giày Tây Nam Oxford Brogue Da Bò', 'Giày Búp Bê Nữ Mũi Tròn Êm Chân', 'Giày Boots Cổ Lửng Da Bò',
                  'Dép Sục Classic Siêu Nhẹ', 'Giày Sneaker Độn Đế Hack Chiều Cao 5cm', 'Giày Tập Gym Nâng Tạ Chống Lật'],
        'specs': ['Đệm Khí Air Giảm Chấn Đàn Hồi Cực Tốt', 'Da Bò Thật 100% Khâu Viền Bền Bỉ', 'Lưới Mesh Thoáng Khí Chống Hôi Chân',
                  'Đế Cao Su Tự Nhiên Chống Trơn Trượt', 'Kháng Khuẩn Khử Mùi Bằng Bọt Biển', 'Quai Dán Tiện Lợi Dễ Điều Chỉnh',
                  'Gót Vuông 5cm Đi Cả Ngày Không Đau Mỏi', 'Siêu Nhẹ Chỉ 190g Nhanh Nhẹn', 'Chống Nước Đi Mưa An Toàn',
                  'Phong Cách Retro Cổ Điển Dễ Phối Đồ', 'Đệm Memory Foam Siêu Mềm Êm Chân', 'Đế Phíp Khâu Chỉ Nổi Thủ Công'],
        'shops': ['Biti\'s Hunter Flagship', 'Nike Official Store', 'Adidas Mall', 'Converse Vietnam', 'Skechers Mall', 'Puma Flagship', 'MLB Korea Store']
    },
    6: {  # Đồ gia dụng thông minh
        'brands': ['Philips', 'Lock&Lock', 'Tefal', 'Sunhouse', 'Panasonic', 'Sharp', 'Xiaomi Smart', 'Kangaroo',
                   'Cuckoo', 'Dyson', 'Deerma', 'Hafele', 'Bear', 'Kalite', 'Toshiba'],
        'types': ['Nồi Chiên Không Dầu Điện Tử', 'Nồi Cơm Điện Cao Tần IH Lòng Niêu', 'Robot Hút Bụi Lau Nhà LiDAR',
                  'Máy Pha Cà Phê Espresso Mini', 'Máy Ép Chậm Trục Ngang Giữ Vitamin', 'Máy Lọc Không Khí Kháng Khuẩn Bụi Mịn',
                  'Bàn Là Hơi Nước Cầm Tay Du Lịch', 'Bếp Từ Đơn Cảm Ứng Mặt Kính', 'Máy Xay Sinh Tố Đa Năng Cối Thủy Tinh',
                  'Nồi Áp Suất Điện Đa Năng 6L', 'Quạt Đứng Động Cơ Inverter Êm Ái', 'Ấm Đun Siêu Tốc Giữ Nhiệt 2 Lớp'],
        'specs': ['Dung Tích Lớn 6.5L Lòng Nồi Chống Dính', 'Kết Nối WiFi Điều Khiển Qua Điện Thoại App',
                  'Công Nghệ Inverter Tiết Kiệm Điện 50%', 'Màng Lọc HEPA H13 Lọc Bụi 99.97%', 'Tự Động Giặt Giẻ Sấy Khô Nhiệt',
                  'Áp Suất Bơm 20 Bar Chuẩn Ý', 'Thép Không Gỉ 304 An Toàn Tuyệt Đối', 'Cảm Ứng Một Chạm Vô Cùng Tiện Lợi',
                  'Công Suất Mạnh Mẽ 1800W Nấu Nhanh', 'Thiết Kế Gấp Gọn Bỏ Túi Tiện Lợi', 'Tự Ngắt An Toàn Chống Trào Chống Cháy'],
        'shops': ['Philips Home Appliances', 'Lock&Lock Official', 'Tefal Flagship', 'Xiaomi Smart Home', 'Sunhouse Mall', 'Panasonic Official', 'Bear Vietnam']
    },
    7: {  # Mỹ phẩm & Sắc đẹp
        'brands': ['L\'Oréal Paris', 'La Roche-Posay', 'Innisfree', 'Cocoon', 'Paula\'s Choice', 'The Ordinary',
                   'Bioderma', 'Maybelline', 'Laneige', 'Vichy', 'Cerave', 'Anessa', 'MAC', 'Kiehl\'s', 'Klairs'],
        'types': ['Serum Phục Hồi Cấp Ẩm Da Hyalu B5', 'Kem Chống Nắng Phổ Rộng Kiềm Dầu SPF50+', 'Son Kem Lì Mịn Môi Lâu Trôi',
                  'Nước Tẩy Trang Micellar Dịu Nhẹ 500ml', 'Sữa Rửa Mặt Tạo Bọt Cho Da Dầu Mụn', 'Kem Dưỡng Ẩm Phục Hồi Màng Da',
                  'Dung Dịch Tẩy Da Chết Hóa Học 2% BHA', 'Mặt Nạ Ngủ Cấp Nước Cho Môi', 'Toner Hoa Cúc Cân Bằng Làm Dịu Da',
                  'Dầu Gội Bưởi Ngăn Rụng Kích Mọc Tóc', 'Mascara Dày Cong Mi Chống Nước', 'Phấn Nước Kiềm Dầu Cushion SPF50+'],
        'specs': ['Chiết Xuất Hyaluronic Acid & Vitamin B5 Căng Mịn', 'Kiềm Dầu 12h Nâng Tone Tự Nhiên Không Vệt Trắng',
                  'Màu Đỏ Đất Thời Thượng Tôn Da Không Khô Môi', 'Không Cồn Không Paraben An Toàn Da Nhạy Cảm',
                  'Độ pH Chuẩn 5.5 Bảo Vệ Màng Ẩm Tự Nhiên', 'Chống Oxy Hóa Chuyên Sâu Tái Tạo Làn Da',
                  'Tinh Chất Cà Phê Đắk Lắk Tẩy Tế Bào Chết', 'Dưỡng Ẩm Sâu Ban Đêm Môi Mọng Hồng',
                  'Thu Nhỏ Lỗ Chân Lông Kiểm Soát Bã Nhờn', 'Đầu Cọ Siêu Mảnh Chống Lem Không Trôi 24h'],
        'shops': ['L\'Oréal Paris Mall', 'La Roche-Posay Official', 'Innisfree Vietnam', 'The Ordinary Store', 'Cocoon Vietnam', 'Maybelline Official', 'Cerave Store']
    },
    8: {  # Đồng hồ & Phụ kiện
        'brands': ['Casio', 'Daniel Wellington', 'Fossil', 'Citizen', 'Seiko', 'Ray-Ban', 'Pedro', 'Charles & Keith',
                   'Xiaomi Band', 'Apple Watch Accessories', 'Tissot', 'Montblanc', 'Julius', 'Garmin'],
        'types': ['Đồng Hồ Nam Dây Da Sapphire Chống Nước', 'Kính Mát Phân Cực Polarized Chống Tia UV400',
                  'Ví Nam Da Bò Thật Dáng Đứng Mini', 'Đồng Hồ Nữ Mặt Tròn Đính Đá Pha Lê',
                  'Vòng Đeo Tay Thông Minh Smart Band Đo Nhịp Tim', 'Thắt Lưng Nam Da Bò Khóa Tự Động Hợp Kim',
                  'Đồng Hồ Thể Thao G-Shock Chống Sốc Chống Nước', 'Túi Đeo Chéo Nam Vải Oxford Chống Thấm',
                  'Balo Laptop Chống Sốc Chống Trộm 15.6 inch', 'Gọng Kính Cận Titan Siêu Nhẹ 8g Dẻo Bền',
                  'Ví Nữ Cầm Tay 2 Ngăn Đựng Điện Thoại', 'Đồng Hồ Cơ Tự Động Automatic Lộ Máy Skeleton'],
        'specs': ['Mặt Kính Sapphire Chống Xước Chống Nước 5ATM', 'Tròng Kính Chống Chói Lóa Bảo Vệ Mắt Đi Nắng',
                  'Chất Liệu Da Bò Ý Thật 100% Càng Dùng Càng Bóng', 'Mặt Số Đính Đá Lấp Lánh Dây Thép Không Gỉ',
                  'Màn Hình AMOLED Pin Khủng 14 Ngày Đo SpO2', 'Mặt Khóa Kim Loại Khắc Laser Sang Trọng Chống Rỉ',
                  'Nhiều Ngăn Thẻ Tích Hợp Khóa Chống Quét Trộm RFID', 'Vải Kháng Nước Đi Mưa Nhẹ Có Cổng Sạc USB',
                  'Dây Đeo Milanese Mắt Lưới Hít Nam Châm Chắc Chắn', 'Bảo Hành Chính Hãng 2 Năm Thay Pin Miễn Phí'],
        'shops': ['Casio Vietnam Store', 'Daniel Wellington Mall', 'Ray-Ban Official', 'Seiko Flagship', 'Fossil Vietnam', 'Tissot Authorized', 'Garmin Vietnam']
    }
}

LOCAL_IMAGES = [
    "/static/images/catalog/0183a26f47c9a49b.jpg", "/static/images/catalog/01d1c6086e4946dd.jpg",
    "/static/images/catalog/033a96827fafddcc.jpg", "/static/images/catalog/09ddcd01f868485a.jpg",
    "/static/images/catalog/0ff14790a138c6fd.jpg", "/static/images/catalog/18971a1f250371e5.jpg",
    "/static/images/catalog/198c46f1c383ac6f.jpg", "/static/images/catalog/1d2b90e9593ea950.jpg",
    "/static/images/catalog/1eb387290b688f38.jpg", "/static/images/catalog/1fd3c541504d3504.jpg",
    "/static/images/catalog/2002820d19e457df.jpg", "/static/images/catalog/285219581b378fb6.jpg",
    "/static/images/catalog/286e4aea119e33c6.jpg", "/static/images/catalog/2ef69a8e8bbebf1e.jpg",
    "/static/images/catalog/42b2f8a7cabd17ed.jpg", "/static/images/catalog/4e7510a29a03b087.jpg",
    "/static/images/catalog/50867512f65f1c41.jpg", "/static/images/catalog/52f555117a200f4b.jpg",
    "/static/images/catalog/5728b0b1a24dfa1f.jpg", "/static/images/catalog/5ba071fa46ae32e6.jpg",
    "/static/images/catalog/5d5f1dc61d25dd14.jpg", "/static/images/catalog/5ebb4aaabcc0b38c.jpg",
    "/static/images/catalog/6aa2092c78deba9b.jpg", "/static/images/catalog/72e1c1864fbf6d4a.jpg",
    "/static/images/catalog/7672a1e11faa7e56.jpg", "/static/images/catalog/76b08251e39e41f3.jpg",
    "/static/images/catalog/7caad0a5922c8026.jpg", "/static/images/catalog/7fc594d5de7b650e.jpg",
    "/static/images/catalog/820c3f01a6b76fb4.jpg", "/static/images/catalog/822f951331e559ae.jpg",
    "/static/images/catalog/902c3c9c4b2832bb.jpg", "/static/images/catalog/92c497a1d1d7cd6f.jpg",
    "/static/images/catalog/9403b33134aa91fe.jpg", "/static/images/catalog/96d1aeaafdf136fe.jpg",
    "/static/images/catalog/98e11662d6942850.jpg", "/static/images/catalog/9c3004c69334bb6f.jpg",
    "/static/images/catalog/a1134c55444510fd.jpg", "/static/images/catalog/a471fbb79218c18e.jpg",
    "/static/images/catalog/afaf9cce48a384a7.jpg", "/static/images/catalog/b4cf053bbe3e044f.jpg",
    "/static/images/catalog/bcb8cd41bc9c1300.jpg", "/static/images/catalog/c05ce10bc673f2bd.jpg",
    "/static/images/catalog/c366d5473a83e25f.jpg", "/static/images/catalog/d6c0e17fac16b3c9.jpg",
    "/static/images/catalog/dc49ee5746f7377e.jpg", "/static/images/catalog/deb5000b89dc7274.jpg",
    "/static/images/catalog/e5f5cf4f395bfea6.jpg", "/static/images/catalog/e72e81ac3b88d8a9.jpg",
    "/static/images/catalog/eab4a26f82b6167f.jpg", "/static/images/catalog/ebe86ff60d7bfbea.jpg",
    "/static/images/catalog/f217f75b74260fd6.jpg", "/static/images/catalog/f798a0176fc49a71.jpg",
    "/static/images/catalog/f8bc2a94f83ea25e.jpg", "/static/images/catalog/fbafab4713bd5cd0.jpg"
]


def populate():
    db_path = config.DB_PATH
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Step 1: Collect all history items across all 8 users
    users = cur.execute('SELECT user_id, features_json FROM muse_user_features').fetchall()
    item_to_rawcat = {}
    for uid, feat_str in users:
        feat = json.loads(feat_str)
        items = feat.get('150_2_180', [])
        cats = feat.get('151_2_180', [])
        for itm, cat in zip(items, cats):
            if itm and itm not in item_to_rawcat:
                item_to_rawcat[itm] = cat

    print(f"Total unique history items to populate: {len(item_to_rawcat)}")

    # Step 2: Try to find extra features (213, 214) from item_features.parquet
    item_file = config.DATASET_DIR / 'raw/item_features.parquet'
    parquet_features = {}
    if item_file.exists():
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(item_file).iter_batches(batch_size=65536):
            for r in batch.to_pylist():
                if r['205'] in item_to_rawcat:
                    parquet_features[r['205']] = r

    print(f"Found genuine 213/214 features for {len(parquet_features)} items in parquet.")

    # Step 3: Get existing products in DB
    existing_products = {r[0]: r[1] for r in cur.execute('SELECT raw_item_id, id FROM products').fetchall()}
    existing_muse_features = {r[0] for r in cur.execute('SELECT raw_item_id FROM muse_item_features').fetchall()}

    # Step 4: Generate unique product details for all history items
    rng = random.Random(42)
    name_counter = {}
    used_names = set(cur.execute('SELECT name FROM products').fetchall())

    inserted_products = 0
    updated_muse_items = 0

    for raw_id, raw_cat in item_to_rawcat.items():
        # Map raw category to Shopee category 1..8
        cat_id = (abs(raw_cat) % 8) + 1
        v = VOCAB[cat_id]

        # Generate a distinct realistic Vietnamese name
        b = rng.choice(v['brands'])
        t = rng.choice(v['types'])
        s = rng.choice(v['specs'])
        base_name = f"{t} {b} {s}"

        name = base_name
        counter = 2
        while name in used_names:
            name = f"{base_name} (Bản {counter})"
            counter += 1
        used_names.add(name)

        # Price generation by category
        if cat_id == 1:
            price = rng.choice([89000, 159000, 249000, 450000, 680000, 950000, 1450000, 2890000, 12500000])
        elif cat_id == 2:
            price = rng.choice([120000, 290000, 480000, 890000, 1590000, 2990000, 4500000])
        elif cat_id == 3:
            price = rng.choice([139000, 189000, 249000, 320000, 450000, 650000])
        elif cat_id == 4:
            price = rng.choice([145000, 199000, 289000, 350000, 490000, 750000])
        elif cat_id == 5:
            price = rng.choice([89000, 180000, 389000, 590000, 890000, 1450000, 2890000])
        elif cat_id == 6:
            price = rng.choice([149000, 280000, 550000, 890000, 1690000, 2890000, 5500000])
        elif cat_id == 7:
            price = rng.choice([95000, 165000, 245000, 380000, 520000, 890000])
        else:
            price = rng.choice([79000, 149000, 280000, 450000, 890000, 1890000, 3800000])

        discount_pct = rng.randint(10, 45)
        original_price = int(price / (1 - discount_pct / 100))
        original_price = round(original_price / 10000) * 10000
        if original_price <= price:
            original_price = price + 50000
        discount_pct = round((original_price - price) / original_price * 100)

        # Image from local set
        img = LOCAL_IMAGES[abs(raw_id) % len(LOCAL_IMAGES)]
        shop = rng.choice(v['shops'])
        sold_count = rng.randint(120, 8900)
        rating_star = round(rng.uniform(4.7, 5.0), 1)
        rating_count = int(sold_count * rng.uniform(0.15, 0.45))
        province_id = rng.choice([1, 2, 3, 4, 13])
        desc = f"{name}. Sản phẩm chính hãng 100% phân phối độc quyền bởi {shop}. Hỗ trợ đổi trả 15 ngày, bảo hành tiêu chuẩn nhà sản xuất. Cam kết chất lượng dịch vụ chuẩn Shopee Mall."

        # Insert or update in products
        if raw_id not in existing_products:
            cur.execute("""
                INSERT INTO products(raw_item_id, name, category_id, price, original_price, discount_percent,
                                     stock, sold_count, rating_star, rating_count, image_url, province_id,
                                     shop_name, is_mall, is_freeship, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?)
            """, (raw_id, name, cat_id, price, original_price, discount_pct, rng.randint(50, 300),
                  sold_count, rating_star, rating_count, img, province_id, shop, desc))
            inserted_products += 1

        # Insert or update in muse_item_features
        feat = parquet_features.get(raw_id, {
            '205': raw_id,
            '206': raw_cat,
            '213': 0,
            '214': 0
        })
        cur.execute("INSERT OR REPLACE INTO muse_item_features(raw_item_id, features_json) VALUES (?, ?)",
                    (raw_id, json.dumps(feat)))
        updated_muse_items += 1

    con.commit()
    print(f"Inserted {inserted_products} new products, updated {updated_muse_items} muse_item_features.")

    # Step 5: Update user_behavior_history so 100% of rows link to real product_id!
    print("Linking user_behavior_history to products...")
    cur.execute("""
        UPDATE user_behavior_history
        SET product_id = (SELECT p.id FROM products p WHERE p.raw_item_id = user_behavior_history.raw_item_id)
        WHERE product_id IS NULL OR product_id NOT IN (SELECT id FROM products)
    """)
    con.commit()

    total_hist = cur.execute('SELECT COUNT(*) FROM user_behavior_history').fetchone()[0]
    matched_hist = cur.execute('SELECT COUNT(*) FROM user_behavior_history WHERE product_id IS NOT NULL').fetchone()[0]
    total_prod = cur.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    total_muse = cur.execute('SELECT COUNT(*) FROM muse_item_features').fetchone()[0]

    print("=" * 60)
    print(f"DATABASE VERIFICATION:")
    print(f"  - Total products in catalog: {total_prod}")
    print(f"  - Total muse_item_features: {total_muse}")
    print(f"  - Total user behavior records: {total_hist}")
    print(f"  - User behavior records with REAL products: {matched_hist} / {total_hist} ({round(matched_hist/total_hist*100, 1)}%)")
    print("=" * 60)

    con.close()


if __name__ == '__main__':
    populate()
