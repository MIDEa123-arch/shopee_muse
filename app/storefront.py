"""Commerce presentation only. Never consumed by the MUSE forward pass.

The source catalog is illustrative, not recovered Taobao merchandise. Keep the
original products/features intact and attach paired names/photos at serialization.
"""
import hashlib
import json
import sqlite3
from functools import lru_cache

from app import config

CATEGORIES = [
    {'slug': 'electronics', 'name': 'Điện tử', 'icon': 'laptop', 'image': '101.webp'},
    {'slug': 'fashion', 'name': 'Thời trang', 'icon': 'shirt', 'image': '83.webp'},
    {'slug': 'beauty', 'name': 'Làm đẹp', 'icon': 'beauty', 'image': '8.webp'},
    {'slug': 'home', 'name': 'Nhà cửa & Đời sống', 'icon': 'appliance', 'image': '47.webp'},
    {'slug': 'shoes', 'name': 'Giày dép', 'icon': 'shoe', 'image': '88.webp'},
    {'slug': 'bags', 'name': 'Túi & Phụ kiện', 'icon': 'bag', 'image': '172.webp'},
    {'slug': 'watches', 'name': 'Đồng hồ', 'icon': 'watch', 'image': '93.webp'},
    {'slug': 'sports', 'name': 'Thể thao', 'icon': 'bag', 'image': '147.webp'},
]

# These are types of the illustrative photographs, never decoded Taobao groups.
TYPE_LABELS = {
    'beauty':'Trang điểm','fragrances':'Nước hoa','skin-care':'Chăm sóc da',
    'furniture':'Nội thất','home-decoration':'Trang trí nhà cửa',
    'kitchen-accessories':'Dụng cụ nhà bếp','kitchen-appliances':'Thiết bị nhà bếp',
    'cookware':'Nồi & chảo','laptops':'Laptop','mens-shirts':'Áo nam',
    'mens-shoes':'Giày nam','womens-shoes':'Giày nữ','mens-watches':'Đồng hồ nam',
    'womens-watches':'Đồng hồ nữ','headphones':'Tai nghe','speakers':'Loa',
    'charging':'Sạc & pin dự phòng','phone-cases':'Ốp điện thoại',
    'camera-accessories':'Phụ kiện quay chụp','smartphones':'Điện thoại',
    'tablets':'Máy tính bảng','womens-clothing':'Trang phục nữ',
    'womens-bags':'Túi xách','womens-jewellery':'Trang sức',
    'sunglasses':'Kính thời trang','sports-accessories':'Dụng cụ thể thao',
    'watches':'Đồng hồ',
}


@lru_cache(maxsize=1)
def template_types():
    source=json.loads((config.ROOT/'app/storefront_source.json').read_text())
    result={p['id']:p['category'] for p in source['products']}
    for ids,kind in [((100,101,107),'headphones'),((99,103),'speakers'),
                     ((102,104,105),'charging'),((108,),'phone-cases'),
                     ((109,110,111,112),'camera-accessories'),
                     ((51,56,61,66),'kitchen-appliances'),((52,68,71),'cookware')]:
        for product_id in ids:result[product_id]=kind
    result[106]='watches'
    return {k:('womens-clothing' if v in ('tops','womens-dresses') else
               'watches' if v in ('mens-watches','womens-watches') else v) for k,v in result.items()}


SALE_STEPS=(10,15,20,25,30,35,40,50)


def sale_original_price(product_id,price):
    """Illustrative flash-sale reference price; the selling price never changes."""
    digest=hashlib.sha256(f'sale:{product_id}'.encode()).digest()
    if digest[0]%100>=20:
        return price
    discount=SALE_STEPS[digest[1]%len(SALE_STEPS)]
    return max(price+1000,round(price*100/(100-discount)/1000)*1000)


@lru_cache(maxsize=2)
def presentation_map(db_path):
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        # initialize() creates this table even for legacy/test databases.
        rows = db.execute('SELECT * FROM product_presentations').fetchall()
    result = {}
    for row in rows:
        data = dict(row)
        data['images'] = json.loads(data.pop('images_json'))
        data['presentation_category'] = data.pop('category_slug')
        data['presentation_source'] = 'DummyJSON · danh mục minh họa'
        data['presentation_is_illustrative'] = True
        kind=template_types().get(data['template_id'])
        data['presentation_type']=kind
        data['presentation_type_name']=TYPE_LABELS.get(kind,'Sản phẩm')
        result[data.pop('product_id')] = data
    return result


def presentation(product_id):
    return presentation_map(str(config.DB_PATH)).get(product_id)


def available_categories(db):
    counts = dict(db.execute('''SELECT d.category_slug,COUNT(*) FROM product_presentations d
        JOIN products p ON p.id=d.product_id WHERE p.stock>0 AND p.source_feature_complete=1
        GROUP BY d.category_slug''').fetchall())
    return [{**c, 'product_count': counts[c['slug']]} for c in CATEGORIES if counts.get(c['slug'])]
