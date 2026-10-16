"""Merchandise identity and purchase policy; never changes checkpoint inputs."""
import re
import unicodedata
import hashlib
import json
from functools import lru_cache
from pathlib import Path


def normalized(value):
    value = unicodedata.normalize('NFD', str(value or '').casefold().replace('đ', 'd'))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in value if unicodedata.category(c) != 'Mn')).split())


def display_name(name):
    # Preserve actual capacity/size variants; discard generated prose/spec blocks.
    def keep_size(match):
        content = match.group(1).strip()
        if re.fullmatch(r'(?i)\d+\s*(?:GB|TB|ml|g|kg|L)(?:\s*[/+]\s*\d+\s*(?:GB|TB|ml|g|kg|L))*', content):
            return ' (' + content + ')'
        return ''
    return ' '.join(re.sub(r'\s*\(([^)]*)\)', keep_size, name or '').split())


def identity(product):
    """Same displayed model, across raw IDs, shops, colors and generated specs."""
    return normalized(display_name(product.get('name', '')).split(' - ', 1)[0])


def kind(product):
    name = normalized(display_name(product.get('name', '')).split(' - ', 1)[0])
    # Specific accessories precede phone/laptop words in an accessory title.
    rules = (
        ('phone-case', ('op dien thoai', 'op iphone', 'bao da dien thoai')),
        ('cable', ('cap sac', 'cap type c', 'cap lightning')),
        ('power-bank', ('pin du phong', 'pin sac du phong')),
        ('wireless-charger', ('de sac',)),
        ('charger', ('cu sac', 'de sac', 'sac nhanh', 'sac da cong')),
        ('laptop-bag', ('balo laptop', 'tui laptop', 'tui chong soc laptop')),
        ('racket-bag', ('bao vot',)),
        ('shuttlecock', ('qua cau long','cau long long vu')),
        ('shoe-insole', ('lot giay','insole')),
        ('shoe-cleaner', ('ve sinh giay','lau giay','khan lau giay')),
        ('shoe-bag', ('tui dung giay','sneaker bag')),
        ('shoelaces', ('day giay','laces')),
        ('shoe-deodorizer', ('khu mui giay','vien khu mui')),
        ('keyboard', ('ban phim',)), ('mouse', ('chuot ',)),
        ('monitor', ('man hinh ',)), ('tablet', ('may tinh bang', 'ipad ', 'xiaomi pad', 'galaxy tab')),
        ('laptop', ('laptop', 'macbook')),
        ('headphones', ('airpods max', 'tai nghe chup', 'wh 1000', 'wh ch', 'tai nghe gaming')),
        ('earbuds', ('airpods', 'true wireless', 'wf 1000', 'nhot tai', 'nhet tai', 'earbuds', 'galaxy buds', 'redmi buds', 'freebuds')),
        ('headphones', ('tai nghe',)), ('speaker', ('loa ',)),
        ('watch', ('dong ho',)),
        ('phone', ('dien thoai', 'iphone', 'samsung galaxy', 'redmi note', 'oppo ', 'vivo ')),
        ('sunscreen', ('chong nang',)), ('serum', ('serum',)),
        ('makeup-remover', ('tay trang',)), ('cleanser', ('sua rua mat',)), ('moisturizer', ('kem duong',)),
        ('lipstick', ('son ',)),
        ('air-fryer', ('noi chien',)), ('robot-vacuum',('robot hut bui',)), ('vacuum', ('hut bui',)),
        ('air-purifier', ('may loc khong khi',)), ('blender', ('may xay',)),
        ('iron', ('ban ui',)), ('cookware', ('chao', 'noi inox')),
        ('lunchbox', ('hop com',)), ('bottle', ('binh giu nhiet', 'binh nuoc')),
        ('milk', ('sua bot', 'sua thanh', 'binh sua')), ('diapers', ('ta quan', 'ta dan')),
        ('toys', ('lego', 'do choi', 'xep hinh')),
        ('racket', ('vot cau long', 'vot tennis')), ('yoga-mat', ('tham tap',)),
        ('resistance-band', ('day khang luc',)), ('roller', ('con lan',)),
        ('tent', ('leu cam trai',)), ('sleeping-bag', ('tui ngu',)),
        ('camp-stove', ('bep gas',)), ('camp-chair', ('ghe xep',)),
        ('sandals', ('sandal', 'dep ')), ('heels', ('giay cao got',)),
        ('flats',('giay bup be',)), ('loafers',('giay luoi',)),
        ('shoes', ('giay ',)), ('socks', ('vo ', 'tat ')),
        ('dress', ('dam ', 'vay maxi', 'vay dam')), ('skirt', ('chan vay',)),
        ('underwear',('quan lot','boxer')), ('shorts',('quan short',)),
        ('pants', ('quan ',)), ('shirt', ('ao so mi',)),
        ('jacket', ('ao khoac', 'ao hoodie', 'ao blazer', 'ao cardigan')),
        ('top', ('ao thun', 'ao polo', 'ao kieu', 'ao croptop')),
        ('bag', ('tui xach', 'balo ')), ('wallet', ('vi da', 'vi nam',)),
        ('glasses', ('kinh mat', 'kinh ram',)),
    )
    for label, terms in rules:
        if label=='monitor' and not name.startswith('man hinh '):continue
        if any(term in name for term in terms):
            return label
    return 'other:' + ' '.join(name.split()[:3])


COMPLEMENTS = {
    'phone': {'charger', 'cable', 'power-bank', 'phone-case', 'earbuds', 'headphones'},
    'tablet': {'charger', 'cable', 'earbuds', 'headphones', 'keyboard'},
    'laptop': {'charger', 'keyboard', 'mouse', 'monitor', 'laptop-bag', 'headphones', 'earbuds'},
    'earbuds': {'charger', 'cable', 'power-bank'},
    'headphones': {'charger', 'cable', 'power-bank'},
    'speaker': {'charger', 'cable', 'power-bank'},
    'charger': {'cable', 'power-bank'}, 'cable': {'charger', 'power-bank'},
    'power-bank': {'cable', 'charger'}, 'phone-case': {'charger', 'cable', 'earbuds'},
    'keyboard': {'mouse', 'monitor', 'laptop-bag'}, 'mouse': {'keyboard', 'monitor'},
    'monitor': {'keyboard', 'mouse', 'headphones'},
    'sunscreen': {'cleanser', 'serum', 'moisturizer', 'makeup-remover', 'lipstick'},
    'serum': {'cleanser', 'sunscreen', 'moisturizer', 'makeup-remover'},
    'moisturizer': {'cleanser', 'sunscreen', 'serum', 'makeup-remover'},
    'cleanser': {'sunscreen', 'serum', 'moisturizer', 'makeup-remover'},
    'makeup-remover': {'cleanser', 'sunscreen', 'serum', 'moisturizer', 'lipstick'},
    'lipstick': {'cleanser', 'sunscreen', 'makeup-remover'},
    'shoes': {'socks', 'bottle', 'shoe-insole','shoe-cleaner','shoe-bag','shoelaces','shoe-deodorizer'}, 'sandals': {'bag', 'glasses'},
    'heels': {'bag', 'dress', 'skirt'},
    'shirt': {'pants', 'shoes', 'watch', 'wallet'}, 'top': {'pants', 'shoes', 'watch'},
    'pants': {'shirt', 'top', 'shoes', 'wallet'}, 'jacket': {'top', 'pants', 'shoes'},
    'shorts': {'top','bottle','shoes'}, 'underwear': set(),
    'dress': {'heels', 'sandals', 'bag'}, 'skirt': {'top', 'heels', 'bag'},
    'watch': {'wallet', 'glasses'}, 'wallet': {'watch', 'glasses'}, 'bag': {'wallet', 'glasses'},
    'air-fryer': {'cookware', 'lunchbox', 'bottle'},
    'cookware': {'lunchbox', 'bottle'}, 'blender': {'bottle', 'lunchbox'},
    'vacuum': set(), 'robot-vacuum':set(), 'iron': set(), 'air-purifier': set(),
    'lunchbox': {'bottle'}, 'bottle': {'lunchbox'},
    # Stage/size/age compatibility is absent. Do not infer feeding or infant
    # toy suitability from a shared category or a high click score.
    'milk': set(), 'diapers': set(), 'toys': set(),
    'racket': {'racket-bag', 'bottle', 'shoes','shuttlecock'}, 'racket-bag': {'bottle', 'shoes','shuttlecock'},
    'shuttlecock': {'racket-bag','bottle'},
    'shoe-insole': {'socks','shoe-cleaner','shoe-bag'},
    'shoe-cleaner': {'shoe-bag','shoelaces'}, 'shoelaces': {'shoe-cleaner','shoe-bag'},
    'shoe-bag': {'shoe-cleaner','socks'}, 'shoe-deodorizer': {'shoe-cleaner','shoe-bag'},
    'yoga-mat': {'resistance-band', 'roller', 'bottle'},
    'roller': {'yoga-mat', 'resistance-band', 'bottle'},
    'resistance-band': {'yoga-mat', 'roller', 'bottle'},
    'tent': {'sleeping-bag', 'camp-stove', 'camp-chair'},
    'sleeping-bag': {'tent', 'camp-stove', 'camp-chair'},
    'camp-stove': {'cookware', 'bottle', 'camp-chair'}, 'camp-chair': {'tent', 'sleeping-bag'},
}
DURABLE_KINDS = {'phone', 'tablet', 'laptop', 'earbuds', 'headphones', 'speaker', 'monitor',
                 'keyboard', 'mouse', 'watch', 'air-fryer', 'blender', 'vacuum', 'iron',
                 'air-purifier', 'racket', 'tent', 'yoga-mat', 'shoes', 'heels', 'sandals',
                 'charger', 'wireless-charger', 'power-bank', 'phone-case', 'laptop-bag',
                 'flats','loafers','robot-vacuum'}
FOOTWEAR_KINDS={'shoes','sandals','heels','flats','loafers'}
for _footwear_type in ('flats','loafers'):
    COMPLEMENTS[_footwear_type]=COMPLEMENTS['shoes']


def is_complement(candidate, focus):
    if identity(candidate) == identity(focus) or kind(candidate) not in COMPLEMENTS.get(kind(focus), set()):
        return False
    name = normalized(candidate['name'])
    focus_name = normalized(focus['name'])
    if kind(focus) == 'laptop' and kind(candidate) == 'charger':
        watts = re.search(r'\b(\d+)w\b', name)
        # Wattage alone does not establish that an Inspiron/gaming laptop can
        # charge through USB-C. Generated parentheses are not evidence either.
        focus_title=normalized(display_name(focus['name']))
        candidate_title=normalized(display_name(candidate['name']))
        if ('pd' not in focus_title.split() or 'pd' not in candidate_title.split()
                or not watts or int(watts[1]) < 45):
            return False
    if kind(focus) == 'phone' and re.search(r'iphone (?:1[5-9]|[2-9][0-9])\b', focus_name) and 'lightning' in name:
        return False
    if kind(candidate)=='cable':
        if kind(focus)=='phone':
            legacy_iphone=bool(re.search(r'iphone (?:[6-9]|1[0-4]|se)\b',focus_name))
            if legacy_iphone and 'lightning' not in name:return False
            if not legacy_iphone and ('lightning' in name or not any(t in name for t in ('type c','usb c'))):return False
        elif 'lightning' in name and 'lightning' not in focus_name:
            return False
    if kind(candidate) == 'phone-case':
        model = re.search(r'iphone \d+(?: pro)?(?: max| plus| mini)?', name)
        focus_model = re.search(r'iphone \d+(?: pro)?(?: max| plus| mini)?', focus_name)
        # A case for the base model need not fit its Pro/Plus version.
        if not model or not focus_model or model[0] != focus_model[0]:
            return False
    if kind(focus)=='racket' and kind(candidate)=='shoes':
        if not any(t in name for t in ('the thao','chay bo','cau long','tennis','sneaker')):
            return False
    if kind(candidate)=='shoelaces' and any(t in focus_name for t in ('khong day','slip on','giay luoi')):
        return False
    if kind(focus)=='racket' and kind(candidate)=='racket-bag':
        return candidate.get('price',0)<=max(1200000,focus.get('price',0))
    if kind(candidate)=='shuttlecock' and 'cau long' not in focus_name:return False
    return candidate.get('price', 0) <= max(1200000, focus.get('price', 0) * 0.5)


def purchase_context(db, user_id):
    """Cancelled orders never suppress goods. Reads only this customer's orders."""
    if not user_id:
        return {'keys': set(), 'recent_kinds': set(), 'items': []}
    rows = [dict(r) for r in db.execute('''SELECT p.*,COALESCE(NULLIF(i.product_name,''),p.name) purchased_name,MAX(o.created_at) purchased_at,
        MAX(o.created_at >= datetime('now','-30 days')) recent_purchase,
        MAX(o.created_at >= datetime('now','-2 days')) hot_purchase
        FROM orders o JOIN order_items i ON i.order_id=o.id JOIN products p ON p.id=i.product_id
        WHERE o.user_id=? AND o.order_status!='Đã hủy'
        GROUP BY p.id ORDER BY purchased_at DESC LIMIT 500''', (user_id,))]
    for row in rows:
        row['name']=row['purchased_name']
    recent_kinds={kind(p) for p in rows if p['recent_purchase'] and kind(p) in DURABLE_KINDS}
    if recent_kinds & {'earbuds','headphones'}:
        recent_kinds.update({'earbuds','headphones'})
    if recent_kinds & FOOTWEAR_KINDS:recent_kinds.update(FOOTWEAR_KINDS)
    if recent_kinds & {'vacuum','robot-vacuum'}:recent_kinds.update({'vacuum','robot-vacuum'})
    return {'keys': {identity(p) for p in rows},
            'recent_kinds': recent_kinds,
            'items': rows}


def exclude_owned(products, purchases, cart=(), *, home=False, manual_category=False):
    cart_keys = {identity(p) for p in cart}
    return [p for p in products if identity(p) not in purchases['keys']
            and identity(p) not in cart_keys
            and (not home or manual_category or kind(p) not in purchases['recent_kinds'])]


def unique_models(products, *, exclude=()):
    exclude=list(exclude)
    seen = {identity(p) for p in exclude}
    photos = {p.get('image_url') for p in exclude if p.get('image_url')}
    result = []
    for product in products:
        key = identity(product)
        photo = product.get('image_url')
        if key in seen or (photo and photo in photos):
            continue
        seen.add(key)
        if photo:
            photos.add(photo)
        result.append(product)
    return result


@lru_cache(maxsize=1)
def illustration_pools():
    from app import config
    from .catalog import demo_photo_families
    source = json.loads((config.ROOT / 'app/storefront_source.json').read_text())['products']
    pools = {key: list(values) for key, values in demo_photo_families().items()}
    # Visual audit: old family labels included people, food, abstract art and
    # unrelated cosmetics. Do not trust those labels merely because they exist.
    rejected = {'033a96827fafddcc', 'bcb8cd41bc9c1300', '42b2f8a7cabd17ed',
                '01f8cffd69f9d4c0', '4487e24fb8e5807c', 'cdb01fceb2090ca8',
                '6fa737d5ce6f8bdc', 'dc49ee5746f7377e', '9be6981611bc490a',
                '930fb238daa2b9ff', '5728b0b1a24dfa1f', 'd6c0e17fac16b3c9',
                '5ba07f1a46ae32e6', 'f46b0667be4e7f51', '2e437a822116bda3',
                '820c3f01a6b76fb4', '551e445610dace62', 'afaf9cce48a384a7',
                'a1134c55444510fd', '2002820d19e457df', '5a03999a3a13dfa4',
                'acb065f4b085b3d'}
    pools = {key: [p for p in values if Path(p).stem not in rejected]
             for key, values in pools.items()}
    pools.update({
        'sunscreen': ['/static/images/merchandise/anessa-milk.png', '/static/images/merchandise/anessa-mild.png'],
        'cleanser': ['/static/images/catalog/bcb8cd41bc9c1300.jpg'],
        'moisturizer': ['/static/images/catalog/42b2f8a7cabd17ed.jpg'],
        'women_pants': ['/static/images/catalog/820c3f01a6b76fb4.jpg'],
        'racket-bag': ['/static/images/merchandise/racket-bag.png'],
        'yoga-mat': ['/static/images/merchandise/yoga-mat.jpg'],
        'bottle': ['/static/images/merchandise/bottle.jpg'],
        'robot-vacuum':pools.get('vacuum',[]),
        'vacuum':[],
    })
    source_types = {'smartphones': 'phone', 'tablets': 'tablet', 'laptops': 'laptop',
                    'fragrances': 'fragrance', 'mens-shirts': 'men_shirt',
                    'mens-shoes': 'sneaker', 'womens-shoes': 'heels',
                    'womens-bags': 'bag', 'womens-jewellery': 'jewellery',
                    'mens-watches': 'watch', 'womens-watches': 'watch'}
    for item in source:
        family = source_types.get(item['category'])
        path = f'/static/images/storefront/{item["id"]}.webp'
        if family and (config.ROOT / path.lstrip('/')).is_file():
            pools.setdefault(family, []).append(path)
            if family in ('phone','tablet','laptop'):
                title=normalized(item['title'])
                brand=next((b for b in ('iphone','samsung','oppo','vivo','realme','ipad','macbook','asus','huawei','lenovo','dell') if b in title),None)
                if brand:pools.setdefault(f'{family}:{brand}', []).append(path)
    for family, ids in {'charger': (104,), 'wireless-charger': (102,), 'power-bank': (105,), 'phone-case': (108,),
                        'cookware': (52, 68, 71), 'bottle': (), 'blender': (51, 61)}.items():
        pools.setdefault(family, []).extend(f'/static/images/storefront/{i}.webp' for i in ids)
    return {key: tuple(dict.fromkeys(p for p in values if (config.ROOT / p.lstrip('/')).is_file()))
            for key, values in pools.items()}


def merchandise_image(product):
    """Type-correct illustration, stable across ID/color variants of one model.

    These assets cannot establish an exact manufacturer/model/color match.
    Unknown types get a placeholder instead of a randomly unrelated photo.
    """
    aliases = {'shoes': 'sneaker', 'sandals': 'sandal', 'headphones': 'headphone',
               'speaker': 'speaker', 'air-fryer': 'air_fryer', 'shirt': 'men_shirt',
               'top': 'men_tshirt', 'jacket': 'men_jacket', 'pants': 'men_pants',
               'dress': 'women_dress', 'skirt': 'women_skirt', 'keyboard': 'keyboard',
               'vacuum': 'vacuum', 'glasses': 'sunglasses'}
    family = kind(product)
    name=normalized(display_name(product.get('name')))
    if family=='mouse':
        photo=next((filename for token,filename in (
            ('mx master 3s','mx-master-3s.png'),('m331','m331.png'),
            ('pebble m350','pebble-m350.png'),('g102','g102.png')) if token in name),None)
        if photo:
            from app import config
            path='/static/images/merchandise/'+photo
            if (config.ROOT/path.lstrip('/')).is_file():return path
    if family=='sunscreen':
        filename='anessa-milk.png' if 'perfect uv milk' in name else 'anessa-mild.png'
        return '/static/images/merchandise/'+filename
    if family in ('phone','tablet','laptop'):
        brand=next((b for b in ('iphone','samsung','oppo','vivo','realme','ipad','macbook','asus','huawei','lenovo','dell') if b in name),None)
        if brand and illustration_pools().get(f'{family}:{brand}'):
            family=f'{family}:{brand}'
    if product.get('category_id') == 4:
        family = {'pants': 'women_pants', 'top': 'women_top', 'shirt': 'women_top',
                  'jacket': 'women_suit'}.get(family, family)
    pool = illustration_pools().get(aliases.get(family, family), ())
    if not pool:
        return '/static/images/placeholder.svg'
    index = int.from_bytes(hashlib.sha256(identity(product).encode()).digest()[:4], 'big') % len(pool)
    return pool[index]
