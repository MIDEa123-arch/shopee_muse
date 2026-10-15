"""Repair legacy template selection and photos, preserving raw IDs and stock."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import config
from app.database import connection
from app.seed_data import PRODUCT_TEMPLATES


def refresh():
    if not config.DEMO_MODE:
        raise SystemExit('This tool is only for demo merchandising data.')
    path=config.ROOT/'static/images/catalog/sources.json'
    photos=json.loads(path.read_text()) if path.exists() else {}
    with connection(write=True) as db:
        if db.execute('SELECT 1 FROM schema_migrations WHERE version=2').fetchone():
            print('Demo catalog already repaired. No changes.')
            return
        db.execute("CREATE TABLE IF NOT EXISTS catalog_before_repair AS SELECT * FROM products")
        counts={}
        for p in db.execute('SELECT id,category_id FROM products ORDER BY id').fetchall():
            category=p['category_id'];index=counts.get(category,0);counts[category]=index+1
            templates=PRODUCT_TEMPLATES[category];name,price,original,image=templates[index%len(templates)]
            variant=index//len(templates)+1;delta=(variant*5000)%30000
            price+=delta;original+=delta
            db.execute('''UPDATE products SET name=?,price=?,original_price=?,discount_percent=?,image_url=? WHERE id=?''',
                (f'{name} (Model #{variant})',price,original,int((original-price)*100/original),photos.get(image.split('?')[0],image),p['id']))
        db.execute('INSERT INTO schema_migrations VALUES (2)')
        print('Demo catalog repaired. Raw IDs, stock, orders and user activity preserved; original merchandising backed up in catalog_before_repair.')


if __name__=='__main__':
    refresh()
