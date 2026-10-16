"""Install an independent, reversible presentation catalog; no model imports.

Fetch paired photos with at most two downloads in flight. SQLite features, original
product rows, histories, cart and orders are never updated by this script.
"""
import hashlib
import json
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from app import config
from app.database import connection, initialize
from app.storefront import CATEGORIES, presentation_map, sale_original_price
from app.native_catalog import MODE,catalog_info

ROOT = config.ROOT
TITLES = {
1:'Mascara Essence Lash Princess',2:'Bảng phấn mắt kèm gương',3:'Phấn phủ dạng hộp',4:'Son môi đỏ',5:'Sơn móng tay đỏ',
6:'Nước hoa Calvin Klein CK One',7:'Nước hoa Chanel Coco Noir',8:'Nước hoa Dior J’adore',9:'Nước hoa Dolce Shine',10:'Nước hoa Gucci Bloom',
11:'Giường gỗ Annibale Colombo',12:'Sofa Annibale Colombo',13:'Tủ đầu giường gỗ anh đào',14:'Ghế văn phòng Knoll Saarinen',15:'Tủ lavabo gỗ kèm gương',
43:'Xích đu trang trí',44:'Khung ảnh cây gia đình',45:'Cây cảnh trang trí để bàn',46:'Chậu cây trang trí',47:'Đèn bàn chụp vải cổ điển',
48:'Xẻng nấu ăn bằng tre',49:'Cốc nhôm màu đen',50:'Phới đánh trứng màu đen',51:'Máy xay sinh tố để bàn',52:'Chảo wok thép carbon',
53:'Thớt nhà bếp',54:'Dụng cụ vắt cam màu vàng',55:'Dụng cụ cắt trứng',56:'Bếp điện đơn',57:'Rây lọc lưới mịn',58:'Nĩa ăn inox',59:'Ly thủy tinh',60:'Dụng cụ bào thực phẩm',
61:'Máy xay cầm tay',62:'Khay làm đá viên',63:'Rây lọc nhà bếp',64:'Dao nhà bếp',65:'Hộp đựng cơm',66:'Lò vi sóng',67:'Giá treo cốc',68:'Chảo nấu ăn',69:'Đĩa ăn',70:'Kẹp gắp thực phẩm màu đỏ',
71:'Nồi inox nắp kính',72:'Xẻng lật thức ăn có khe',73:'Kệ đựng gia vị',74:'Thìa ăn inox',75:'Khay đựng đồ',76:'Cây cán bột bằng gỗ',77:'Dụng cụ gọt vỏ màu vàng',
78:'Laptop Apple MacBook Pro 14 inch xám',79:'Laptop ASUS Zenbook Pro hai màn hình',80:'Laptop Huawei MateBook X Pro',81:'Laptop Lenovo Yoga 920',82:'Laptop Dell XPS 13 9300',
83:'Áo sơ mi kẻ xanh đen',84:'Áo thun nam Gigabyte Aorus',85:'Áo sơ mi nam kẻ ô',86:'Áo sơ mi nam tay ngắn',87:'Áo sơ mi nam họa tiết caro',
88:'Giày Nike Air Jordan 1 đỏ đen',89:'Giày bóng chày Nike',90:'Giày thể thao Puma Future Rider',91:'Giày thể thao trắng ngà phối đỏ',92:'Giày sneaker trắng phối đỏ',
93:'Đồng hồ dây da nâu',94:'Đồng hồ Longines Master Collection',95:'Đồng hồ Rolex Cellini mặt đen',96:'Đồng hồ Rolex Cellini Moonphase',97:'Đồng hồ Rolex Datejust',98:'Đồng hồ Rolex Submariner',
99:'Loa thông minh Amazon Echo Plus',100:'Tai nghe Apple AirPods',101:'Tai nghe Apple AirPods Max bạc',102:'Đế sạc không dây Apple AirPower',103:'Loa Apple HomePod mini xám',104:'Củ sạc Apple iPhone',105:'Pin dự phòng Apple MagSafe',106:'Apple Watch Series 4 vàng',107:'Tai nghe không dây Beats Flex',108:'Ốp iPhone 12 MagSafe màu mận',109:'Chân đỡ điện thoại đơn',110:'Đèn hỗ trợ quay chụp điện thoại',111:'Gậy chụp ảnh tự sướng',112:'Chân máy quay studio',
118:'Xà phòng rửa tay Attitude Super Leaves',119:'Sữa tắm Olay Ultra Moisture bơ hạt mỡ',120:'Sữa dưỡng da Vaseline Men',
121:'Điện thoại Apple iPhone 5s',122:'Điện thoại Apple iPhone 6',123:'Điện thoại Apple iPhone 13 Pro',124:'Điện thoại Apple iPhone X',125:'Điện thoại OPPO A57',126:'Điện thoại OPPO F19 Pro Plus',127:'Điện thoại OPPO K1',128:'Điện thoại realme C35',129:'Điện thoại realme X',130:'Điện thoại realme XT',131:'Điện thoại Samsung Galaxy S7',132:'Điện thoại Samsung Galaxy S8',133:'Điện thoại Samsung Galaxy S10',134:'Điện thoại vivo S1',135:'Điện thoại vivo V9',136:'Điện thoại vivo X21',
137:'Bóng bầu dục',138:'Bóng chày',139:'Găng tay bóng chày',140:'Bóng rổ',141:'Vành rổ bóng rổ',142:'Bóng cricket',143:'Gậy cricket',144:'Mũ bảo hộ cricket',145:'Bộ cọc cricket',146:'Quả cầu lông',147:'Bóng đá',148:'Bóng golf',149:'Gậy golf sắt',150:'Gậy bóng chày kim loại',151:'Bóng tennis',152:'Vợt tennis',153:'Bóng chuyền',
154:'Kính mát gọng đen',155:'Kính mát kiểu cổ điển',156:'Kính mát phối xanh đen',157:'Kính thời trang dự tiệc',158:'Kính mát thời trang',
159:'Máy tính bảng iPad mini 2021 Starlight',160:'Máy tính bảng Samsung Galaxy Tab S8+ xám',161:'Máy tính bảng Samsung Galaxy Tab trắng',
162:'Váy xanh dáng xòe',163:'Váy mùa hè nữ',164:'Váy nữ màu xám',165:'Váy ngắn dáng xòe',166:'Váy họa tiết tartan',
172:'Túi xách nữ màu xanh',173:'Túi da nữ Heshe',174:'Túi xách nữ Prada',175:'Balo da nhân tạo màu trắng',176:'Túi xách nữ màu đen',
177:'Đầm dạ hội nữ màu đen',178:'Bộ áo corset da và chân váy',179:'Bộ corset cùng chân váy đen',180:'Váy nữ họa tiết',181:'Bộ trang phục Marni đỏ đen',182:'Khuyên tai pha lê xanh',183:'Khuyên tai oval xanh',184:'Khuyên tai phong cách nhiệt đới',
185:'Dép nữ phối đen nâu',186:'Giày cao gót Calvin Klein',187:'Giày nữ ánh vàng',188:'Giày cao gót Pampi',189:'Giày nữ màu đỏ',190:'Đồng hồ IWC Ingenieur Automatic',191:'Đồng hồ nữ Rolex Cellini Moonphase',192:'Đồng hồ nữ Rolex Datejust',193:'Đồng hồ nữ màu vàng',194:'Đồng hồ đeo tay nữ',
}
SOURCE_GROUPS = {
    'electronics': ['laptops','mobile-accessories','smartphones','tablets'],
    'fashion': ['mens-shirts','tops','womens-dresses'],
    'beauty': ['beauty','fragrances','skin-care'],
    'home': ['furniture','home-decoration','kitchen-accessories'],
    'shoes': ['mens-shoes','womens-shoes'],
    'bags': ['womens-bags','womens-jewellery','sunglasses'],
    'watches': ['mens-watches','womens-watches'],
    'sports': ['sports-accessories'],
}


def build():
    initialize()
    with connection() as db:
        if catalog_info(db)['mode']!=MODE:
            raise ValueError('Migrate the original Taobao catalog before attaching a storefront')
    source_file = ROOT/'app/storefront_source.json'
    source = json.loads(source_file.read_text())
    products = [p for p in source['products'] if p['id'] in TITLES]
    image_dir = ROOT/'static/images/storefront'; image_dir.mkdir(parents=True,exist_ok=True)
    def fetch(p):
        from PIL import Image
        target = image_dir/f'{p["id"]}.webp'
        if target.exists() and target.stat().st_size>100:
            with Image.open(target) as im:
                im.verify()
            return
        temp = target.with_suffix('.download')
        subprocess.run(['curl','--fail','--location','--silent','--show-error','--retry','2',
            '--max-time','30','--max-filesize','2000000','-A','Mozilla/5.0',p['thumbnail'],'-o',str(temp)],check=True)
        if temp.stat().st_size<100:
            raise ValueError(f'Empty photo for {p["id"]}')
        # Verify actual decoded content instead of accepting HTML/error payloads.
        with Image.open(temp) as im:
            im.verify()
        temp.replace(target)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(fetch,products))
    pools = {c['slug']:[p for p in products if p['category'] in SOURCE_GROUPS[c['slug']]] for c in CATEGORIES}
    if not all(pools.values()):
        raise ValueError('A display category has no paired product photos')
    # Snapshot the complete app state before attaching display metadata.
    backup = config.DB_PATH.parent/'backups'/('before-storefront-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.db')
    backup.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(config.DB_PATH) as src,sqlite3.connect(backup) as dest:
        src.backup(dest)
    rows=[]
    with connection() as db:
        originals = list(db.execute("SELECT id,category_id FROM products WHERE catalog_source='taobao-mm' ORDER BY id"))
    for item in originals:
        # Reproducible illustration assignment. This is NOT category recovery or
        # a semantic interpretation of anonymous SCL embeddings.
        digest = hashlib.sha256(str(item['category_id']).encode()).digest()
        category = CATEGORIES[int.from_bytes(digest[:4],'big') % len(CATEGORIES)]
        pool = pools[category['slug']]
        p = pool[int.from_bytes(hashlib.sha256(str(item['id']).encode()).digest()[:4],'big') % len(pool)]
        # Explicit fixed demo conversion, not a current FX quote or Taobao price.
        price = max(10000,round(p['price']*25000/1000)*1000)
        image = f'/static/images/storefront/{p["id"]}.webp'
        description = f'{TITLES[p["id"]]}. Ảnh và tên cùng lấy từ một sản phẩm mẫu trong danh mục DummyJSON. Thông tin và giá phục vụ trải nghiệm mua sắm mô phỏng; không phải hàng hóa gốc của ID Taobao.'
        rows.append((item['id'],TITLES[p['id']],category['slug'],category['name'],image,json.dumps([image]),p.get('brand',''),description,price,sale_original_price(item['id'],price),'Lumi · '+category['name'],p['id']))
    with connection(write=True) as db:
        db.executemany('''INSERT INTO product_presentations(product_id,name,category_slug,category_name,image_url,images_json,brand,description,price,original_price,shop_name,template_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET
            name=excluded.name,category_slug=excluded.category_slug,category_name=excluded.category_name,
            image_url=excluded.image_url,images_json=excluded.images_json,brand=excluded.brand,
            description=excluded.description,price=excluded.price,original_price=excluded.original_price,
            shop_name=excluded.shop_name,template_id=excluded.template_id''',rows)
        info={'version':1,'paired_templates':len(products),'mapped_items':len(rows),
              'source_url':'https://dummyjson.com/docs/products',
              'illustrative':True,'original_product_metadata':False,'model_inputs_unchanged':True,
              'pricing':'Fixed illustrative 25,000 VND per source price unit; not a market quote',
              'backup':str(backup)}
        db.execute("INSERT OR REPLACE INTO catalog_settings VALUES ('storefront',?)",(json.dumps(info),))
    presentation_map.cache_clear()
    return info


if __name__=='__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
