"""Presentation invariance and commerce consistency using an isolated DB."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import config
from app.database import connection, initialize
from app.main import app
from app.recommender.native import native_ranking
from app.recommender.service import service
from app.storefront import presentation_map
from scripts.build_storefront import build


class StorefrontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=config.DB_PATH
        cls.temp=tempfile.TemporaryDirectory()
        config.DB_PATH=Path(cls.temp.name)/'store.db'
        with sqlite3.connect(cls.original) as src,sqlite3.connect(config.DB_PATH) as dst:
            src.backup(dst)
        initialize()
        def digest(db,table):
            return hashlib.sha256(repr(db.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()).encode()).hexdigest()
        protected=('products','muse_item_features','muse_user_features','user_behavior_history','cart_items','orders','order_items','users','addresses')
        with sqlite3.connect(config.DB_PATH) as db:
            before={t:digest(db,t) for t in protected}
        cls.info=build()
        with sqlite3.connect(config.DB_PATH) as db:
            after={t:digest(db,t) for t in protected}
        assert before==after,'Display installation changed protected data'
        cls.ctx=TestClient(app);cls.client=cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None,None,None)
        config.DB_PATH=cls.original;presentation_map.cache_clear();native_ranking.cache.clear();cls.temp.cleanup()

    def test_exact_ranking_invariance_all_eight_profiles(self):
        for uid in range(1,9):
            native_ranking.cache.clear()
            with patch('app.storefront.presentation',return_value=None):
                before=native_ranking.recommend(service,uid,'home',None,60,write_logs=False)
                before_scores=dict(next(reversed(native_ranking.cache.values()))[1])
            native_ranking.cache.clear()
            after=native_ranking.recommend(service,uid,'home',None,60,write_logs=False)
            after_scores=dict(next(reversed(native_ranking.cache.values()))[1])
            self.assertEqual(before_scores,after_scores)  # Every one of the 8,192 scores.
            self.assertEqual([(p['id'],p['p_click']) for p in before['items']],[(p['id'],p['p_click']) for p in after['items']])
            self.assertNotEqual(before['items'][0]['name'],after['items'][0]['name'])
            self.assertTrue(all(p['presentation_is_illustrative'] for p in after['items']))

    def test_photo_title_pairs_and_original_category_separation(self):
        source={p['id']:p for p in json.loads((config.ROOT/'app/storefront_source.json').read_text())['products']}
        with connection() as db:
            rows=db.execute('SELECT p.category_id,p.source_category_id,d.* FROM products p JOIN product_presentations d ON d.product_id=p.id').fetchall()
        for row in rows:
            self.assertIn(row['template_id'],source)
            self.assertEqual(row['image_url'],f'/static/images/storefront/{row["template_id"]}.webp')
            self.assertTrue((config.ROOT/row['image_url'].lstrip('/')).is_file())
            self.assertGreaterEqual(row['category_id'],10001)
        catalog=self.client.get('/api/catalog').json()
        self.assertEqual(len(catalog['storefront_categories']),8)
        self.assertEqual(sum(c['product_count'] for c in catalog['storefront_categories']),8192)
        self.assertFalse(catalog['source']['titles_available'])

    def test_search_filters_prices_and_unchanged_scores(self):
        self.client.post('/api/auth/demo-login',json={'user_id':1})
        result=self.client.get('/api/products?q=tai%20nghe&sort=relevance&page_size=60').json()
        self.assertGreater(result['total'],10)
        self.assertTrue(all('tai nghe' in p['name'].lower() for p in result['items']))
        self.assertTrue(result['personalized'])
        price_result=self.client.get('/api/products?display_category=electronics&min_price=100000&max_price=2000000&sort=price_asc&page_size=60').json()
        prices=[p['price'] for p in price_result['items']]
        self.assertGreater(len(prices),0)
        self.assertEqual(prices,sorted(prices))
        self.assertTrue(all(100000<=v<=2000000 for v in prices))
        self.assertTrue(all(p['presentation_category']=='electronics' for p in price_result['items']))
        all_result=native_ranking.recommend(service,1,'home',None,60,write_logs=False)
        filtered=native_ranking.recommend(service,1,'home',None,60,write_logs=False,display_category='electronics')
        self.assertTrue(all(p['presentation_category']=='electronics' for p in filtered['items']))
        # A presentation filter restricts candidates, and never boosts scores.
        filtered_map={p['id']:p['p_click'] for p in filtered['items']}
        for p in all_result['items']:
            if p['id'] in filtered_map:self.assertEqual(p['p_click'],filtered_map[p['id']])
        self.assertEqual(self.client.get('/api/products?display_category=unknown').json()['total'],0)
        self.assertTrue(self.client.get('/api/search/suggestions?q=tai%20nghe').json()['autocomplete'])

    def test_cart_quote_and_order_use_same_presentation(self):
        # A new account keeps existing profiles, carts and orders untouched.
        email='store-check@example.test'
        response=self.client.post('/api/auth/register',json={'full_name':'Kiểm thử cửa hàng','email':email,'phone':'0912345678','password':'TestPass123!'})
        self.assertEqual(response.status_code,201,response.text)
        p=self.client.get('/api/products/1').json()
        self.assertEqual(self.client.post('/api/cart',json={'product_id':1,'quantity':2}).status_code,201)
        cart=self.client.get('/api/cart').json()
        self.assertEqual(cart['items'][0]['name'],p['name']);self.assertEqual(cart['subtotal'],p['price']*2)
        address=self.client.post('/api/account/addresses',json={'recipient_name':'Kiểm thử cửa hàng','phone':'0912345678','province_id':1,'detail':'12 Đường Kiểm Thử, Phường Mẫu','label':'Nhà riêng','is_default':True}).json()
        body={'address_id':address['id'],'payment_method':'COD','voucher_code':'','use_coins':False}
        quote=self.client.post('/api/checkout/quote',json=body).json()
        self.assertEqual(quote['items'][0]['image_url'],p['image_url'])
        direct=self.client.post('/api/checkout/quote',json={**body,'buy_now':{'product_id':1,'quantity':2}}).json()
        self.assertEqual(quote['subtotal'],direct['subtotal'])
        order=self.client.post('/api/orders',json={**body,'quote_token':quote['quote_token'],'expected_total':quote['total'],'idempotency_key':'store-check-123456789'} )
        self.assertEqual(order.status_code,201,order.text)
        item=order.json()['items'][0]
        self.assertEqual(item['product_name'],p['name']);self.assertEqual(item['unit_price'],p['price']);self.assertEqual(item['image_url'],p['image_url'])
        self.assertEqual(self.client.post(f'/api/orders/{order.json()["id"]}/cancel').status_code,200)

    def test_renamed_voucher_restrictions_are_preserved(self):
        from app.services.checkout import voucher_issue
        with connection() as db:
            new_user={'id':-1,'member_tier':'Bạc'}
            issue=voucher_issue(db,{'code':'TAOBAOVIP100K','end_date':'2099-12-31',
                'min_order_value':0,'discount_type':'fixed'},new_user,2000000,30000)
            self.assertEqual(issue,'Dành cho thành viên Vàng và Kim Cương.')
            user_id=db.execute("SELECT user_id FROM orders WHERE order_status!='Đã hủy' LIMIT 1").fetchone()[0]
            issue=voucher_issue(db,{'code':'TAOBAO30K','end_date':'2099-12-31',
                'min_order_value':0,'discount_type':'fixed'},{'id':user_id},1000000,30000)
            self.assertEqual(issue,'Chỉ áp dụng cho đơn hàng đầu tiên.')

    def sample_product(self,template_id):
        with connection() as db:
            return db.execute('''SELECT p.id FROM products p JOIN product_presentations d ON d.product_id=p.id
                WHERE d.template_id=? AND p.source_feature_complete=1 AND p.stock>0 ORDER BY p.id LIMIT 1''',(template_id,)).fetchone()[0]

    def test_contextual_phone_recommendations_keep_scores_and_remove_duplicates(self):
        phone=self.sample_product(123)
        result=native_ranking.recommend(service,1,'home',None,60,write_logs=False,
            presentation_policy='contextual',focus_product_id=phone)
        self.assertTrue(result['meta']['model_used'])
        self.assertGreater(len(result['items']),1)
        self.assertTrue(all(p['presentation_type']=='smartphones' for p in result['items']))
        templates=[p['template_id'] for p in result['items']]
        self.assertEqual(len(templates),len(set(templates)))
        self.assertNotIn(123,templates)
        scores=result['items'];self.assertEqual([p['p_click'] for p in scores],sorted([p['p_click'] for p in scores],reverse=True))
        stored=next(reversed(native_ranking.cache.values()))[1]
        self.assertTrue(all(p['p_click']==stored[int(p['raw_item_id'])] for p in scores))
        self.assertEqual(result['meta']['merchandise_context']['label'],'Điện thoại')
        original=native_ranking.recommend(service,1,'home',None,60,write_logs=False)
        self.assertFalse(original['meta']['merchandise_context']['enabled'])
        self.assertGreater(len({p['presentation_type'] for p in original['items']}),1)
        manual=native_ranking.recommend(service,1,'home',None,60,write_logs=False,
            display_category='beauty',presentation_policy='contextual',focus_product_id=phone)
        self.assertTrue(all(p['presentation_category']=='beauty' for p in manual['items']))

    def test_related_items_are_same_type_without_self_or_duplicate_photos(self):
        for template in (123,78,100,8,88):
            product_id=self.sample_product(template)
            kind=self.client.get(f'/api/products/{product_id}').json()['presentation_type']
            result=native_ranking.recommend(service,None,'similar',product_id,60,write_logs=False,presentation_policy='contextual')
            self.assertGreater(len(result['items']),0,template)
            self.assertTrue(result['meta']['model_used'])
            self.assertTrue(all(p['presentation_type']==kind and p['template_id']!=template for p in result['items']))
            self.assertEqual(len(result['items']),len({p['template_id'] for p in result['items']}))
            expected=service.model.similarities(int(self.client.get(f'/api/products/{product_id}').json()['raw_item_id']),[int(p['raw_item_id']) for p in result['items']])
            for p,score in zip(result['items'],expected):self.assertAlmostEqual(p['similarity'],score,places=6)
        lone=self.sample_product(108)
        empty=native_ranking.recommend(service,None,'similar',lone,60,write_logs=False,presentation_policy='contextual')
        self.assertEqual(empty['items'],[])
        self.assertEqual(empty['meta']['empty_reason'],'no_other_products_in_context')

    def test_live_interest_cart_and_explicit_browse_do_not_reinterpret_original_history(self):
        self.client.post('/api/auth/register',json={'full_name':'Khách theo ngữ cảnh','phone':'0912345678',
            'email':'context-shop@example.test','password':'ContextPass123!'})
        phone=self.sample_product(123);laptop=self.sample_product(78)
        before=self.client.get('/api/recommendations?presentation_policy=contextual').json()
        self.assertEqual(before['meta']['merchandise_context']['source'],'browse')
        self.client.post(f'/api/recommendations/behavior/{phone}')
        after=self.client.get('/api/recommendations?presentation_policy=contextual').json()
        self.assertTrue(all(p['presentation_type']=='smartphones' for p in after['items']))
        self.assertEqual(after['meta']['merchandise_context']['source'],'recent_web_action')
        self.client.post('/api/cart',json={'product_id':phone,'quantity':1})
        cart=self.client.get('/api/recommendations?touchpoint=cart&presentation_policy=contextual').json()
        self.assertTrue(all(p['presentation_type']=='smartphones' and p['template_id']!=123 for p in cart['items']))
        self.client.post('/api/cart',json={'product_id':laptop,'quantity':1})
        cart=self.client.get('/api/recommendations?touchpoint=cart&presentation_policy=contextual&limit=60').json()
        self.assertEqual(set(cart['meta']['merchandise_context']['types']),{'smartphones','laptops'})
        self.assertTrue(all(p['presentation_type'] in ('smartphones','laptops') and p['template_id'] not in (123,78) for p in cart['items']))
        after=self.client.get('/api/recommendations?presentation_policy=contextual').json()
        self.assertTrue(all(p['presentation_type']=='laptops' for p in after['items']))
        browse=self.client.get('/api/recommendations?presentation_policy=browse&limit=60').json()
        self.assertGreater(len({p['presentation_type'] for p in browse['items']}),1)
        self.assertEqual(len(browse['items']),len({p['template_id'] for p in browse['items']}))

    def test_unique_catalog_and_guest_context_validation(self):
        self.client.post('/api/auth/logout')
        catalog=self.client.get('/api/products?unique_products=true&page_size=60').json()
        self.assertEqual(catalog['total'],157)
        self.assertEqual(len(catalog['items']),len({p['template_id'] for p in catalog['items']}))
        phone=self.sample_product(123)
        result=self.client.get(f'/api/recommendations?presentation_policy=contextual&focus_product_id={phone}').json()
        self.assertTrue(all(p['presentation_type']=='smartphones' for p in result['items']))
        self.assertFalse(result['meta']['model_used'])
        self.assertIsNone(self.client.get('/api/auth/me').json()['user'])
        self.assertEqual(self.client.get('/api/recommendations?presentation_policy=contextual&focus_product_id=999999999').status_code,404)
        self.assertEqual(self.client.get('/api/recommendations?presentation_policy=bad').status_code,422)
        with patch.object(service,'model',None):
            fallback=self.client.get(f'/api/recommendations?presentation_policy=contextual&focus_product_id={phone}').json()
            self.assertTrue(all(p['presentation_type']=='smartphones' for p in fallback['items']))
            self.assertFalse(fallback['meta']['model_used'])

    def test_complementary_bundle_endpoint_and_golf_pairing(self):
        bundle=self.client.get('/api/recommendations/bundle').json()
        self.assertIn('focus',bundle)
        self.assertIn('items',bundle)
        self.assertIn('pricing',bundle)
        self.assertGreater(len(bundle['items']),0)
        self.assertGreaterEqual(bundle['pricing']['savings'],0)

        # Specifically test golf equipment bundle
        golf_res=self.client.get('/api/recommendations/bundle?focus_product_id=153').json()
        self.assertEqual(golf_res['focus']['name'],'Bóng golf')
        item_names=[i['name'] for i in golf_res['items']]
        self.assertIn('Gậy golf sắt',item_names)

        # Phone bundle
        phone=self.sample_product(123)
        phone_bundle=self.client.get(f'/api/recommendations/bundle?focus_product_id={phone}').json()
        phone_items=[i['presentation_type'] for i in phone_bundle['items']]
        self.assertTrue(any(t in ('charging','phone-cases','headphones','tablets') for t in phone_items))

    def test_search_suggestions_with_history_and_price_tier(self):
        self.client.post('/api/auth/demo-login',json={'user_id':1})
        res=self.client.get('/api/search/suggestions').json()
        self.assertIn('trending',res)
        self.assertIn('personalized',res)
        self.assertGreater(len(res['trending']),0)
        self.assertGreater(len(res['personalized']),0)

        recs=self.client.get('/api/recommendations?presentation_policy=browse&limit=24').json()
        self.assertIn('price_affinity',recs['meta'])
        self.assertIn(recs['meta']['price_affinity']['tier'],('budget','mid','premium','all'))


if __name__=='__main__':unittest.main()
