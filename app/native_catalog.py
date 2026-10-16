"""Vietnamese presentation of anonymous Taobao-MM IDs, without invented metadata."""
import hashlib
import json
from functools import lru_cache

MODE = 'taobao_native_v1'


def catalog_info(db):
    row = db.execute("SELECT value FROM catalog_settings WHERE key='source'").fetchone()
    return json.loads(row[0]) if row else {'mode': 'legacy_demo'}


@lru_cache(maxsize=2048)
def identity_svg(product_id, category_id):
    """An ID illustration, explicitly not an image reconstructed from embeddings."""
    digest = hashlib.sha256(f'{product_id}:{category_id}'.encode()).digest()
    hue = round(category_id * 137.508) % 360
    shapes = []
    for index in range(6):
        x = 42 + (index % 3) * 83
        y = 42 + (index // 3) * 83
        size = 32 + digest[index] % 34
        radius = (3, 16, 40)[digest[index + 8] % 3]
        shapes.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{radius}" '
                      f'fill="hsl({hue} 48% {32 + index * 7}%)" opacity=".9" '
                      f'transform="rotate({digest[index+16]%35-17} {x+size/2} {y+size/2})"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 270">'
            f'<rect width="300" height="270" fill="hsl({hue} 36% 94%)"/>'
            '<circle cx="265" cy="20" r="100" fill="white" opacity=".4"/>'
            + ''.join(shapes) + f'<text x="25" y="244" font-family="monospace" font-size="13" '
            f'fill="hsl({hue} 25% 35%)">TB / {product_id:05d}</text></svg>')
