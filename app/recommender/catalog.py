"""Context for the Vietnamese demo display; independent of learned Taobao features."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def curated_demo_titles():
    data=json.loads((Path(__file__).parent/'demo_catalog.json').read_text())
    return {name for names in data.values() for name in names}


def product_kind(name):
    name=name.casefold()
    kinds=('kem chống nắng','bàn phím','màn hình','củ sạc','cáp sạc','pin dự phòng',
           'tai nghe','máy hút bụi','robot hút bụi','máy pha cà phê','nồi chiên',
           'nồi cơm','đồng hồ','kính mát','kính râm','laptop','chuột','serum','son','loa')
    return next((kind for kind in kinds if kind in name),' '.join(name.split()[:3]))


@lru_cache(maxsize=1)
def demo_photo_families():
    return json.loads((Path(__file__).parent/'demo_photos.json').read_text())


def has_matching_demo_photo(product):
    """Stock photos cover main product families, not the generated accessories.

    E.g. a headphone photo is unsuitable for an ear-pad or headphone stand card.
    Keep those catalog rows intact but avoid promoting them as visual suggestions.
    """
    prefixes={
        1:('laptop','màn hình','bàn phím','chuột','củ sạc','cáp sạc','pin dự phòng'),
        2:('tai nghe','loa'),
        3:('áo thun','áo polo','áo sơ mi','áo khoác','áo hoodie','áo bomber','quần'),
        4:('đầm','váy đầm','váy maxi','chân váy','áo kiểu','áo sơ mi','áo croptop','áo cardigan'),
        5:('giày','dép'),
        6:('nồi chiên','robot hút bụi','máy hút bụi','máy pha cà phê','máy xay','quạt'),
        7:('serum','kem chống nắng','son'),
        8:('đồng hồ','ví','kính mát','kính râm'),
    }
    name=product['name'].casefold();category=product['category_id']
    if not name.startswith(prefixes.get(category,())):
        return False
    if category==1:
        family=next((value for prefix,value in (
            ('laptop','laptop'),('màn hình','monitor'),('bàn phím','keyboard'),('chuột','mouse'))
            if name.startswith(prefix)),'charger')
        families=(family,)
    elif category==2:
        if name.startswith('loa'):
            families=('speaker',)
        elif any(term in name for term in ('tws','airpods','nhét tai','in-ear','earbud','wf-','buds')):
            families=('earbuds',)
        elif any(term in name for term in ('chụp tai','headphone','wh-','quietcomfort','kiểm âm','over-ear')):
            families=('headphone',)
        else:
            families=('earbuds','headphone')
    elif category==3:
        families=('men_pants',) if name.startswith('quần') else ('men_shirt',) if name.startswith('áo sơ mi') else ('men_tshirt',) if name.startswith(('áo polo','áo thun')) else ('men_jacket',)
    elif category==4:
        families=('women_skirt',) if name.startswith('chân váy') else ('women_top',) if name.startswith('áo') else ('women_dress',)
    elif category==5:
        families=('sneaker','sandal','leather_shoe','heels')
    elif category==6:
        families=('vacuum',) if 'hút bụi' in name else ('coffee_maker',) if 'cà phê' in name else ('blender',) if 'xay' in name else ('fan',) if name.startswith('quạt') else ('air_fryer',)
    elif category==7:
        families=('serum',) if name.startswith('serum') else ('sunscreen',) if name.startswith('kem chống nắng') else ('lipstick',)
    else:
        families=('watch',) if name.startswith('đồng hồ') else ('wallet',) if name.startswith('ví') else ('sunglasses',)
    photos=demo_photo_families()
    return any(product['image_url'] in photos.get(family,[]) for family in families)
