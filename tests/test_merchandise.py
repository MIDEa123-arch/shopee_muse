"""Purchase/identity regression using a tiny generated SQLite DB; no model load."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config
from app.database import connection, initialize, public_product
from app.recommender.merchandise import (identity, kind, display_name, is_complement,
    purchase_context, exclude_owned, merchandise_image)
from app.recommender.service import RecommendationService
from app.recommender.commerce import personalized_deals, complementary_bundle


def item(name, price=500000, category=9, **extra):
    return {'name':name,'price':price,'category_id':category,**extra}


class IdentityTests(unittest.TestCase):
    def test_same_model_other_color_shop_and_raw_id_is_not_new_merchandise(self):
        a=item('Apple iPhone 15 Pro 128GB VN/A (Camera 48MP) - Titan Đen',id=1)
        b=item('Apple iPhone 15 Pro 128GB VN/A (Màn hình OLED) - Xanh',id=999)
        self.assertEqual(identity(a),identity(b))
        self.assertNotEqual(identity(a),identity(item('Apple iPhone 16 Pro 128GB VN/A - Đen')))

    def test_real_capacity_difference_is_preserved(self):
        self.assertNotEqual(identity(item('Điện thoại Xiaomi Redmi (8GB / 128GB) - Đen')),
                            identity(item('Điện thoại Xiaomi Redmi (12GB / 256GB) - Đen')))
        self.assertIn('(8GB / 128GB)',display_name('Xiaomi Redmi (8GB / 128GB) (Màn hình rực rỡ) - Đen'))

    def test_accessories_not_misclassified_by_phone_or_laptop_words(self):
        self.assertEqual(kind(item('Điện thoại Cáp sạc Type-C to Lightning Anker')), 'cable')
        self.assertEqual(kind(item('Balo laptop chống nước')), 'laptop-bag')
        self.assertEqual(kind(item('Máy tính bảng iPad Air M2')), 'tablet')
        self.assertEqual(kind(item('Apple iPhone 15 Pro')), 'phone')
        self.assertEqual(kind(item('Bàn phím cơ Keychron K2',category=2)), 'keyboard')
        self.assertEqual(kind(item('Đồng hồ Samsung Galaxy Watch')), 'watch')
        self.assertEqual(kind(item('Tai nghe Samsung Galaxy Buds FE')), 'earbuds')
        self.assertEqual(kind(item('Nước tẩy trang Effaclar')), 'makeup-remover')
        self.assertNotEqual(kind(item('Nước tẩy trang Effaclar')),kind(item('Sữa rửa mặt CeraVe')))
        self.assertEqual(kind(item('Máy tính bảng Xiaomi Pad 6 màn hình 2.8K 144Hz')),'tablet')
        self.assertEqual(kind(item('Samsung Galaxy Z Flip6 5G màn hình ngoài lớn')),'phone')
        self.assertEqual(kind(item('Màn hình LG UltraGear 27GR75Q 2K')),'monitor')
        self.assertNotEqual(kind(item('Quần lót nam Boxer')),kind(item('Quần tây nam')))
        self.assertNotEqual(kind(item('Giày búp bê đính nơ')),kind(item('Giày chạy bộ Nike')))

    def test_phone_and_laptop_accessory_compatibility(self):
        phone=item('Apple iPhone 15 Pro 128GB',30000000)
        self.assertFalse(is_complement(item('Cáp sạc Type-C to Lightning Apple'),phone))
        self.assertFalse(is_complement(item('Ốp iPhone 12 MagSafe'),phone))
        self.assertFalse(is_complement(item('Ốp iPhone 15 MagSafe'),phone))
        self.assertFalse(is_complement(item('Ốp điện thoại trong suốt'),phone))
        self.assertTrue(is_complement(item('Ốp iPhone 15 Pro MagSafe'),phone))
        self.assertTrue(is_complement(item('Củ sạc Apple 20W Type-C'),phone))
        self.assertFalse(is_complement(item('Laptop Dell XPS',20000000),phone))
        laptop=item('Laptop Dell XPS',20000000,1)
        self.assertFalse(is_complement(item('Củ sạc Apple 20W Type-C'),laptop))
        self.assertFalse(is_complement(item('Củ sạc Anker 67W GaN'),laptop))
        self.assertTrue(is_complement(item('Củ sạc Type-C PD 67W'),item('Laptop sạc USB-C PD 65W',20000000,1)))
        self.assertFalse(is_complement(item('Cáp sạc Type-C to Lightning Apple'),item('Samsung Galaxy S24 Ultra',20000000)))
        self.assertFalse(is_complement(item('Cáp sạc Type-C to Type-C'),item('Apple iPhone 14 Pro',20000000)))
        self.assertTrue(is_complement(item('Cáp sạc Type-C to Lightning Apple'),item('Apple iPhone 14 Pro',20000000)))

    def test_type_matched_images_are_stable_across_catalog_variants(self):
        serum=item('Serum Hyalu B5 (Dưỡng da) - Đen',category=7)
        same=item('Serum Hyalu B5 (Cấp ẩm) - Xanh',category=7)
        self.assertEqual(merchandise_image(serum),merchandise_image(same))
        self.assertNotIn('/storefront/1.webp',merchandise_image(serum))
        self.assertNotEqual(merchandise_image(serum),merchandise_image(item('Son Black Rouge',category=7)))
        self.assertIn('/catalog/',merchandise_image(item('Bàn phím Keychron',category=2)))
        self.assertEqual(merchandise_image(item('Hàng chưa xác định')), '/static/images/placeholder.svg')

    def test_visually_mislabeled_assets_cannot_return_to_recommendations(self):
        self.assertNotIn('42b2f8a7cabd17ed',merchandise_image(item('Serum Hyalu B5',category=7)))
        self.assertIn('/merchandise/anessa-',merchandise_image(item('Kem chống nắng Anessa',category=7)))
        self.assertNotIn('a1134c55444510fd',merchandise_image(item('Robot hút bụi Dreame',category=6)))
        self.assertNotIn('820c3f01a6b76fb4',merchandise_image(item('Quần tây nam',category=3)))
        self.assertNotIn('cdb01fceb2090ca8',merchandise_image(item('Tai nghe AirPods Pro 2',category=2)))
        self.assertIn('/storefront/12',merchandise_image(item('Apple iPhone 15 Pro')))
        self.assertIn('/storefront/13',merchandise_image(item('Samsung Galaxy S24 Ultra')))
        self.assertNotIn('/storefront/102.',merchandise_image(item('Củ sạc Apple 20W Type-C')))


class PurchaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(config,'DB_PATH',Path(self.tmp.name)/'fixture.db');self.patch.start()
        initialize()
        self.svc=RecommendationService()
        self.products=[
            (1,'Apple iPhone 15 Pro 128GB VN/A - Đen',9,30000000),
            (2,'Apple iPhone 15 Pro 128GB VN/A - Trắng',9,29000000),
            (3,'Samsung Galaxy S24 Ultra',9,28000000),
            (4,'Củ sạc Anker 67W GaN',9,400000),
            (5,'Tai nghe Apple AirPods Pro 2',2,1000000),
            (6,'Tai nghe Apple AirPods Pro 2 - Trắng',2,900000),
            (7,'Tai nghe true wireless Sony WF-1000XM5',2,2000000),
            (8,'Laptop Dell XPS',1,20000000),
            (9,'Bàn phím Keychron K2',2,1000000),
            (10,'Cáp sạc Type-C to Lightning Apple',2,200000),
            (11,'Kem chống nắng Anessa 60ml',7,400000),
            (12,'Son Black Rouge',7,200000),
            (13,'Áo sơ mi nam',3,300000),
            (14,'Giày Nike Air Force',5,900000),
            (15,'Ốp iPhone 12 MagSafe',9,300000),
            (16,'Samsung Galaxy S25 Ultra',9,35000000),
        ]
        with connection(write=True) as db:
            for cid in range(1,12):db.execute('INSERT INTO categories(id,name,slug) VALUES (?,?,?)',(cid,f'Danh mục {cid}',str(cid)))
            db.execute("INSERT INTO provinces(id,name,type,region) VALUES (1,'Hà Nội','Thành phố','Miền Bắc')")
            for uid in (1,2):db.execute('INSERT INTO users(id,full_name,email,phone,password_hash) VALUES (?,?,?,?,?)',(uid,f'Khách {uid}',f'{uid}@test.invalid','0912345678','test'))
            for pid,name,cat,price in self.products:
                db.execute('''INSERT INTO products(id,raw_item_id,name,category_id,price,original_price,discount_percent,
                    stock,sold_count,rating_star,image_url,province_id,shop_name,catalog_source)
                    VALUES (?,?,?,?,?,?,30,10,1000,5,?,1,'Shop thử','tiki-vn')''',
                    (pid,10000+pid,name,cat,price,price*2,'/static/images/placeholder.svg'))
            db.execute("INSERT INTO catalog_settings VALUES ('source',?)",(json.dumps({'mode':'vietnam_tiki_v1'}),))

    def tearDown(self):
        self.patch.stop();self.tmp.cleanup()

    def purchase(self,pid,status='Chờ xác nhận',user=1,old=False):
        with connection(write=True) as db:
            oid=db.execute('''INSERT INTO orders(order_code,user_id,total_goods_amount,shipping_fee,final_payment_amount,
                order_status,recipient_name,recipient_phone,shipping_address) VALUES (?,?,?,?,?,?,?,?,?)''',
                (f'O-{pid}-{user}',user,100,0,100,status,'Khách','0912345678','Hà Nội')).lastrowid
            db.execute('INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES (?,?,1,100)',(oid,pid))
            if old:db.execute("UPDATE orders SET created_at=datetime('now','-31 days') WHERE id=?",(oid,))

    def test_recent_purchase_suppresses_owned_variants_and_durable_type_on_home(self):
        self.purchase(1)
        result=self.svc.recommend(1,limit=24)
        self.assertTrue(result['items'])
        self.assertFalse(any(kind(p)=='phone' for p in result['items']))
        self.assertEqual(result['meta']['purchase_policy']['excluded_models'],1)
        self.assertIn(kind(result['items'][0]),{'charger','earbuds','headphones','power-bank','cable','phone-case'})

    def test_home_category_cannot_bypass_owned_type_cooldown(self):
        self.purchase(1)
        result=self.svc.recommend(1,category_id=9,limit=24)
        self.assertFalse(any(kind(p)=='phone' for p in result['items']))
        self.assertFalse({1,2}&{p['id'] for p in result['items']})

    def test_bought_charger_does_not_trigger_another_charger_after_bought_phone(self):
        self.purchase(1)
        self.purchase(4)
        with connection() as db:owned=purchase_context(db,1)
        self.assertIn('charger',owned['recent_kinds'])
        other=item('Củ sạc Apple 20W Type-C')
        self.assertEqual(exclude_owned([other],owned,home=True),[])
        self.assertEqual(exclude_owned([other],owned,home=True,manual_category=True),[other])

    def test_cancelled_order_does_not_suppress_and_other_user_is_isolated(self):
        self.purchase(1,status='Đã hủy')
        with connection() as db:self.assertEqual(purchase_context(db,1)['keys'],set())
        self.purchase(5,user=2)
        with connection() as db:
            self.assertEqual(purchase_context(db,1)['keys'],set())
            self.assertTrue(purchase_context(db,2)['keys'])

    def test_after_cooldown_allow_other_models_keep_owned_model_excluded(self):
        self.purchase(1,status='Đã giao',old=True)
        with connection() as db:owned=purchase_context(db,1)
        self.assertEqual(owned['recent_kinds'],set())
        self.assertTrue(owned['keys'])
        with connection() as db:rows=[dict(r) for r in db.execute('SELECT * FROM products WHERE id IN (1,2,3)')]
        self.assertEqual([p['id'] for p in exclude_owned(rows,owned,home=True)],[3])

    def test_order_snapshot_preserves_owned_identity_after_catalog_name_changes(self):
        self.purchase(1)
        with connection(write=True) as db:
            db.execute('UPDATE order_items SET product_name=? WHERE product_id=1',(self.products[0][1],))
            db.execute("UPDATE products SET name='Samsung Galaxy S26 Ultra' WHERE id=1")
        with connection() as db:owned=purchase_context(db,1)
        self.assertIn(identity(item(self.products[0][1])),owned['keys'])
        self.assertNotIn(identity(item('Samsung Galaxy S26 Ultra')),owned['keys'])

    def test_cart_does_not_recommend_another_phone_or_cart_color_variant(self):
        with connection(write=True) as db:db.execute('INSERT INTO cart_items(user_id,product_id,quantity) VALUES (1,1,1)')
        result=self.svc.recommend(1,touchpoint='cart')
        self.assertTrue(result['items'])
        self.assertTrue(all(kind(p) in {'charger','earbuds','headphones','power-bank','cable','phone-case'} for p in result['items']))
        self.assertFalse(any('lightning' in p['name'].lower() for p in result['items']))

    def test_detail_distinct_models_same_type_price_and_no_filler(self):
        result=self.svc.recommend(None,'similar',1,limit=24)
        self.assertTrue(result['items'])
        self.assertTrue(all(kind(p)=='phone' and 15000000<=p['price']<=60000000 for p in result['items']))
        self.assertNotIn(2,[p['id'] for p in result['items']])
        self.assertEqual(len(result['items']),len({identity(p) for p in result['items']}))
        self.assertEqual(self.svc.recommend(None,'similar',8)['items'],[])

    def test_purchased_earbuds_absent_from_home_deals_and_bundle(self):
        self.purchase(5)
        with connection() as db:
            deals=personalized_deals(db,1,12)
            bundle=complementary_bundle(db,1,1)
        for p in deals['items']+bundle['items']:
            self.assertNotEqual(identity(p),identity(item('Tai nghe Apple AirPods Pro 2')))
        self.assertFalse(any(kind(p)=='earbuds' for p in self.svc.recommend(1)['items']))
        self.assertFalse(any(kind(p)=='headphones' for p in self.svc.recommend(1)['items']))

    def test_serialization_preserves_model_id_and_uses_type_image(self):
        with connection() as db:p=dict(db.execute('SELECT * FROM products WHERE id=9').fetchone())
        result=public_product(p)
        self.assertEqual(result['raw_item_id'],str(p['raw_item_id']))
        self.assertEqual(result['category_id'],p['category_id'])
        self.assertEqual(result['price'],p['price'])
        self.assertIn('/catalog/',result['image_url'])

    def test_high_scoring_wrong_product_cannot_escape_the_context_filter(self):
        class Features(dict):
            def register_products(self,products):
                for p in products:self[p['raw_item_id']]=p
        class Scorer:
            items=Features()
            def predict(self,uid,ids):
                return [.99 if raw in (10002,10003) else .1234567 for raw in ids],{'history_length':1000}
            def similarities(self,target,ids):return [.99 if raw==10008 else .234567 for raw in ids]
        self.svc.model=Scorer()
        self.purchase(1)
        result=self.svc.recommend(1,'home')
        self.assertTrue(result['meta']['model_used'])
        self.assertFalse(any(kind(p)=='phone' for p in result['items']))
        self.assertTrue(all(p['p_click']==.1234567 for p in result['items']))
        detail=self.svc.recommend(1,'complementary',1)
        self.assertTrue(detail['items'])
        self.assertTrue(all(is_complement(p,item('Apple iPhone 15 Pro 128GB',30000000)) for p in detail['items']))


if __name__=='__main__':unittest.main()
