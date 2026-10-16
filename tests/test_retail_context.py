"""Scenario contracts in a tiny generated DB, never a production DB copy."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import connection
from app.main import app
from app.security import current_user
from app.recommender.service import service
from app.recommender.retail import attributes,query_matches
from app.recommender.merchandise import kind, identity, is_complement
import test_merchandise as fixtures


class Features(dict):
    def register_products(self, products):
        for p in products:self[p['raw_item_id']]=p


class Scorer:
    def __init__(self, broken=False):self.items=Features();self.broken=broken;self.calls=[]
    def predict(self, uid, ids):
        if self.broken:raise RuntimeError('test failure')
        self.calls.append(list(ids))
        # Wrong electronic goods deliberately receive the highest neural score.
        return [0.99 if kind(self.items[i]) in ('phone','laptop','charger') else .1234567 for i in ids],{'history_length':1,'cold_start':True}
    def similarities(self, focus, ids):return [.8 for i in ids]


class ScenarioTests(unittest.TestCase):
    setUp=fixtures.PurchaseTests.setUp
    tearDown=fixtures.PurchaseTests.tearDown
    purchase=fixtures.PurchaseTests.purchase

    def add(self,pid,name,cat=2,price=400000):
        with connection(write=True) as db:
            db.execute('''INSERT INTO products(id,raw_item_id,name,category_id,price,original_price,discount_percent,
                stock,sold_count,rating_star,image_url,province_id,shop_name,catalog_source)
                VALUES (?,?,?,?,?,?,25,100,1000,5,'/static/images/placeholder.svg',1,'Shop thử','tiki-vn')''',
                (pid,10000+pid,name,cat,price,price*2))

    def order_id(self,pid):
        with connection() as db:return db.execute('SELECT order_id FROM order_items WHERE product_id=? ORDER BY id DESC LIMIT 1',(pid,)).fetchone()[0]

    def sports(self):
        self.add(30,'Vợt cầu lông Yonex Astrox 88D Pro',11,1500000)
        self.add(31,'Bao vợt cầu lông Yonex 2 ngăn',11,400000)
        self.add(32,'Bình giữ nhiệt Lock&Lock LHC4131 450ml',11,300000)
        self.add(33,'Giày da tây Oxford',5,500000)
        self.purchase(30)
        self.svc.model=Scorer()
        return self.order_id(30)

    def test_mouse_retains_three_other_models_even_with_shared_photos(self):
        for pid,name in ((20,'Chuột Logitech MX Master 3S'),(21,'Chuột Logitech M331 Silent Plus'),
                         (22,'Chuột Logitech G102 Lightsync RGB'),(23,'Chuột Logitech Pebble M350')):
            self.add(pid,name)
        from app.recommender import retail
        original=retail.public_product
        def same_photo(p):return {**original(p),'image_url':'/static/images/catalog/shared.jpg'}
        with patch.object(retail,'public_product',side_effect=same_photo):
            result=self.svc.recommend(None,'similar',20,6)
        self.assertEqual(len(result['items']),3)
        self.assertEqual(len({identity(p) for p in result['items']}),3)
        self.assertTrue(all(kind(p)=='mouse' for p in result['items']))
        self.assertEqual(result['meta']['retrieval']['eligible_models'],3)

    def test_top_popular_color_copies_cannot_starve_a_rare_product_kind(self):
        for pid in range(100,350):self.add(pid,f'Apple iPhone 15 Pro 128GB VN/A - Màu {pid}',9,30000000)
        self.add(1000,'Chuột Logitech MX Master 3S')
        self.add(1001,'Chuột Logitech Pebble M350')
        self.add(1002,'Chuột Logitech G102')
        result=self.svc.recommend(None,'similar',1000,6)
        self.assertEqual(len(result['items']),2)
        self.assertTrue(all(kind(p)=='mouse' for p in result['items']))

    def test_short_assortment_keeps_same_type_alternatives_with_honest_price_label(self):
        self.add(40,'Máy tính bảng Xiaomi Pad 6 màn hình 144Hz',9,700000)
        self.add(41,'Máy tính bảng iPad Air M2',9,8000000)
        result=self.svc.recommend(None,'similar',40)
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['items'][0]['similar_price_band'],'broader')
        self.assertTrue(result['meta']['retrieval']['broader_price'])
        self.assertEqual(kind(result['items'][0]),'tablet')

    def test_bought_laptop_is_suppressed_in_home_tab_deals_and_offers(self):
        self.purchase(8)
        self.add(30,'Laptop Dell Inspiron',1,18000000)
        self.add(31,'Laptop Lenovo Legion',1,21000000)
        for tp in ('home','deals'):
            for cat in (None,1):
                result=self.svc.recommend(1,tp,category_id=cat)
                self.assertFalse(any(kind(p)=='laptop' for p in result['items']))
        result=self.svc.recommend(1,'home')
        self.assertFalse(any(kind(p)=='charger' for p in result['items']))
        similar=self.svc.recommend(1,'similar',8)
        self.assertEqual(similar['items'],[])
        self.assertEqual(similar['meta']['empty_reason'],'recent_purchase_type')

    def test_sports_order_cannot_include_high_scoring_electronics(self):
        oid=self.sports()
        for tp in ('orders','post_purchase'):
            result=self.svc.recommend(1,tp,order_id=oid)
            self.assertTrue(result['items'])
            self.assertTrue(all(kind(p) in {'racket-bag','bottle','shoes'} for p in result['items']))
            self.assertFalse(any(p['id']==33 for p in result['items']))
            self.assertTrue(all(p['p_click']==.1234567 for p in result['items']))
            self.assertEqual(result['meta']['focus_product_ids'],[30])
            self.assertFalse(result['meta']['semantic_mapping_verified'])

    def test_selected_older_order_wins_over_latest_electronics_order(self):
        sports_order=self.sports();self.purchase(8)
        result=self.svc.recommend(1,'orders',order_id=sports_order)
        self.assertEqual(result['meta']['order_id'],sports_order)
        self.assertTrue(all(kind(p) in {'racket-bag','bottle','shoes'} for p in result['items']))

    def test_multi_item_order_uses_every_item_instead_of_first_product(self):
        oid=self.sports()
        with connection(write=True) as db:
            db.execute('INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES (?,1,1,30000000)',(oid,))
        result=self.svc.recommend(1,'orders',order_id=oid)
        self.assertEqual(set(result['meta']['focus_product_ids']),{1,30})
        self.assertTrue(any(kind(p)=='charger' for p in result['items']))
        self.assertTrue(any(kind(p)=='racket-bag' for p in result['items']))

    def test_cancelled_and_other_customers_order_never_becomes_context(self):
        oid=self.sports()
        self.purchase(8,user=2)
        other=self.order_id(8)
        with self.assertRaises(HTTPException) as caught:self.svc.recommend(1,'orders',order_id=other)
        self.assertEqual(caught.exception.status_code,404)
        with connection(write=True) as db:db.execute("UPDATE orders SET order_status='Đã hủy' WHERE id=?",(oid,))
        result=self.svc.recommend(1,'orders',order_id=oid)
        self.assertEqual(result['items'],[])
        self.assertEqual(result['meta']['empty_reason'],'cancelled_order')

    def test_order_snapshot_used_even_if_current_catalog_name_changes(self):
        oid=self.sports()
        with connection(write=True) as db:
            db.execute("UPDATE order_items SET product_name='Vợt cầu lông Yonex Astrox 88D Pro' WHERE order_id=?",(oid,))
            db.execute("UPDATE products SET name='Laptop Dell mới' WHERE id=30")
        result=self.svc.recommend(1,'orders',order_id=oid)
        self.assertTrue(result['items'])
        self.assertTrue(all(kind(p) in {'racket-bag','bottle','shoes'} for p in result['items']))

    def test_only_selected_cart_items_create_the_context(self):
        self.sports()
        with connection(write=True) as db:
            db.execute('INSERT INTO cart_items(user_id,product_id,quantity,is_selected) VALUES (2,30,1,1)')
            db.execute('INSERT INTO cart_items(user_id,product_id,quantity,is_selected) VALUES (2,1,1,0)')
        result=self.svc.recommend(2,'cart')
        self.assertTrue(result['items'])
        self.assertEqual(result['meta']['focus_product_ids'],[30])
        self.assertFalse(any(kind(p) in {'charger','phone','laptop'} for p in result['items']))

    def test_model_failure_removes_scores_and_does_not_relax_merchandise(self):
        oid=self.sports();self.svc.model=Scorer(broken=True)
        result=self.svc.recommend(1,'orders',order_id=oid)
        self.assertTrue(result['items'])
        self.assertFalse(result['meta']['model_used'])
        self.assertTrue(all('p_click' not in p and p['recommendation_source']=='catalog' for p in result['items']))
        self.assertTrue(all(kind(p) in {'racket-bag','bottle','shoes'} for p in result['items']))

    def test_generated_specs_not_used_as_actual_compatibility_evidence(self):
        tags=attributes({'name':'Chuột Logitech Pebble M350 (Gaming / 8000 DPI / RGB)'})
        self.assertNotIn('gaming',tags)
        self.assertIn('wireless',tags)
        self.assertFalse(query_matches({'name':'Samsung Galaxy Z Flip6 màn hình ngoài lớn'},'màn hình'))
        self.assertFalse(query_matches({'name':'Laptop Dell (Bàn phím RGB)'},'bàn phím'))
        self.assertTrue(query_matches({'name':'Màn hình LG 27 inch'},'màn hình'))

    def test_clothing_gender_and_formula_stage_are_not_overridden_by_model_scores(self):
        self.add(60,'Áo sơ mi nam Oxford',3)
        self.add(61,'Áo sơ mi nam đũi',3)
        self.add(62,'Áo sơ mi nữ nơ cổ',4)
        result=self.svc.recommend(1,'similar',60)
        self.assertTrue(result['items'])
        self.assertTrue(all(p['category_id']==3 for p in result['items']))
        self.add(70,'Sữa bột Meiji số 0 800g',10)
        self.add(71,'Sữa thanh Meiji số 0',10)
        self.add(72,'Sữa bột Meiji số 9 800g',10)
        from app.recommender import retail
        with retail._cache_lock:retail._cache.clear()
        result=self.svc.recommend(1,'similar',70)
        self.assertTrue(result['items'])
        self.assertTrue(all('số 0' in p['name'] for p in result['items']))

    def test_no_quality_percentage_borrowed_from_taobao_offline_auc(self):
        self.svc.model=Scorer()
        result=self.svc.recommend(1)
        self.assertFalse(result['quality']['available'])
        self.assertEqual(result['quality']['reason'],'illustrative_catalog_not_evaluated')

    def test_retail_catalog_pagination_counts_models_after_price_and_province_filters(self):
        self.add(80,'Chuột Logitech M185 - Đen',2,300000)
        self.add(81,'Chuột Logitech M185 - Xám',2,310000)
        self.add(49982,'Chuột Logitech M170',2,200000)
        client=TestClient(app)
        data=client.get('/api/products?q=chuot&unique_products=true&sort=price_asc&page_size=1').json()
        self.assertEqual(data['total'],2)
        self.assertEqual(data['pages'],2)
        self.assertEqual(data['items'][0]['id'],49982)
        data=client.get('/api/products?q=chuot&unique_products=true&min_price=305000').json()
        self.assertEqual(data['total'],1)
        self.assertEqual(data['items'][0]['id'],81)
        shop=client.get('/api/products?q=Shop%20thử&unique_products=true').json()
        self.assertTrue(shop['items'])

    def test_authenticated_order_api_checks_owner_and_returns_order_context(self):
        oid=self.sports()
        app.dependency_overrides[current_user]=lambda:{'id':1}
        try:
            with patch.object(service,'model',self.svc.model):
                client=TestClient(app)
                result=client.get(f'/api/recommendations?touchpoint=orders&order_id={oid}').json()
                self.assertTrue(result['items'])
                self.assertEqual(result['meta']['order_id'],oid)
                self.assertEqual(client.get('/api/recommendations?touchpoint=orders&order_id=99999').status_code,404)
        finally:app.dependency_overrides.pop(current_user,None)

    def test_order_illustration_correction_does_not_rewrite_stored_snapshot(self):
        oid=self.sports()
        wrong='/static/images/storefront/121.webp'
        with connection(write=True) as db:
            db.execute('UPDATE order_items SET image_url=? WHERE order_id=?',(wrong,oid))
        app.dependency_overrides[current_user]=lambda:{'id':1}
        try:
            result=TestClient(app).get('/api/orders').json()
            item=next(o for o in result if o['id']==oid)['items'][0]
            self.assertNotEqual(item['image_url'],wrong)
            self.assertEqual(item['snapshot_image_url'],wrong)
            with connection() as db:self.assertEqual(db.execute('SELECT image_url FROM order_items WHERE order_id=?',(oid,)).fetchone()[0],wrong)
        finally:app.dependency_overrides.pop(current_user,None)

    def test_curated_enrichment_preserves_referenced_rows_features_and_is_idempotent(self):
        import json
        from pathlib import Path
        from scripts.install_retail_curated import install,MANIFEST
        for pid in (100,101,102):self.add(pid,'Chuột Logitech Pebble M350 - Màu '+str(pid))
        self.purchase(102)
        with connection() as db:
            before={p['id']:dict(p) for p in db.execute('SELECT * FROM products WHERE id IN (100,101,102)')}
        entries=json.loads(MANIFEST.read_text())['products'][:1]
        with connection(write=True) as db:
            result=install(db,entries,Path(self.tmp.name)/'backups',apply=True)
        self.assertEqual(result['ids'],[101])
        self.assertTrue(Path(result['backup']).is_file())
        with connection() as db:
            after={p['id']:dict(p) for p in db.execute('SELECT * FROM products WHERE id IN (100,101,102)')}
            self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
            repeated=install(db,entries,Path(self.tmp.name)/'backups',apply=True)
        self.assertEqual(repeated['applied'],0)
        self.assertEqual(before[100],after[100]);self.assertEqual(before[102],after[102])
        for field in ('raw_item_id','source_category_id','source_city_id','source_province_id','source_feature_complete'):
            self.assertEqual(before[101][field],after[101][field])


if __name__=='__main__':unittest.main()
