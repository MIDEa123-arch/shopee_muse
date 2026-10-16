"""Commerce invariants and actual checkpoint integration, using an isolated DB copy.

Run: python -m unittest discover -s tests -v
Requires httpx; no mutations are made to the real customer database.
"""
import concurrent.futures
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient
from app import config
from app.database import connection
from app.main import app
from app.recommender.service import service


class StoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_db=config.DB_PATH
        cls.tmp=tempfile.TemporaryDirectory()
        config.DB_PATH=Path(cls.tmp.name)/'test.db'
        fixture=cls.original_db
        with sqlite3.connect(fixture) as source:
            if source.execute("SELECT 1 FROM sqlite_master WHERE name='catalog_settings'").fetchone():
                row=source.execute("SELECT value FROM catalog_settings WHERE key='migration_backup'").fetchone()
                if row:
                    fixture=Path(row[0])
        # This suite retains the old commerce/legacy-ranking contracts. Native
        # ranking and provenance have their own independent suite in test_native.
        with sqlite3.connect(fixture) as source,sqlite3.connect(config.DB_PATH) as target:
            source.backup(target)
            cls.catalog=source.execute('SELECT price,is_freeship,shop_name,id FROM products').fetchall()
        cls.context=TestClient(app)
        cls.client=cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None,None,None)
        config.DB_PATH=cls.original_db
        cls.tmp.cleanup()

    def setUp(self):
        self.client.cookies.clear()
        with connection(write=True) as db:
            for table in ('reviews','order_items','orders','cart_items','sessions','reset_challenges','auth_attempts','wishlist','audit_events'):
                db.execute(f'DELETE FROM {table}')
            db.execute('UPDATE products SET stock=100')
            db.executemany('UPDATE products SET price=?,is_freeship=?,shop_name=? WHERE id=?',self.catalog)
            db.execute('UPDATE users SET wallet_balance=2500000,shopee_coins=85000 WHERE id IN (1,2)')
            db.execute("UPDATE user_vouchers SET status='available'")
            db.execute("DELETE FROM user_behavior_history WHERE action_type='demo_interest'")
        self.login(1)

    def login(self,uid,client=None):
        result=(client or self.client).post('/api/auth/demo-login',json={'user_id':uid})
        self.assertEqual(result.status_code,200,result.text)
        return result.json()['user']

    def address(self,uid=1):
        with connection() as db:
            return db.execute('SELECT id FROM addresses WHERE user_id=? ORDER BY is_default DESC LIMIT 1',(uid,)).fetchone()[0]

    def body(self,client=None,**kwargs):
        body={'address_id':self.address(),'payment_method':'COD','idempotency_key':'test-order-unique-0001',**kwargs}
        quote=(client or self.client).post('/api/checkout/quote',json=body)
        return {**body,'quote_token':quote.json().get('quote_token','0'*64)}

    def add(self,pid=1,quantity=1,client=None):
        result=(client or self.client).post('/api/cart',json={'product_id':pid,'quantity':quantity})
        self.assertEqual(result.status_code,201,result.text)

    def test_catalog_search_unicode_raw_ids_and_provinces(self):
        catalog=self.client.get('/api/catalog').json()
        self.assertEqual(len(catalog['provinces']),34)
        names={p['name'] for p in catalog['provinces']}
        self.assertIn('Hưng Yên',names);self.assertNotIn('Bình Dương',names)
        result=self.client.get('/api/products',params={'q':'ban phim','sort':'price_asc'}).json()
        self.assertGreater(result['total'],0)
        self.assertIsInstance(result['items'][0]['raw_item_id'],str)
        self.assertEqual([p['price'] for p in result['items']],sorted(p['price'] for p in result['items']))
        self.assertEqual(self.client.get('/api/products',params={'q':"%' OR 1=1 --"}).json()['total'],0)
        self.assertEqual(self.client.get('/api/products?page_size=100000').status_code,422)
        offers=self.client.get('/api/offers').json()['items']
        self.assertEqual(len(offers),6)
        self.assertEqual(len({p['image_url'] for p in offers}),6)
        self.assertTrue(all(p['stock']>0 and p['discount_percent']>0 for p in offers))

    def test_guest_and_cross_origin_protection(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/cart').status_code,401)
        self.assertIsNone(self.client.get('/api/auth/me').json()['user'])
        result=self.client.post('/api/auth/demo-login',json={'user_id':1},headers={'Origin':'https://evil.example'})
        self.assertEqual(result.status_code,403)

    def test_cart_ownership_stock_and_selection(self):
        self.add()
        item=self.client.get('/api/cart').json()['items'][0]
        self.assertEqual(self.client.put('/api/cart/'+str(item['cart_item_id']),json={'quantity':101}).status_code,422)
        self.assertEqual(self.client.put('/api/cart/'+str(item['cart_item_id']),json={'quantity':1,'is_selected':False}).status_code,200)
        self.assertEqual(self.client.post('/api/checkout/quote',json={'address_id':self.address()}).status_code,400)
        self.login(2)
        self.assertEqual(self.client.delete('/api/cart/'+str(item['cart_item_id'])).status_code,404)
        self.assertEqual(self.client.get('/api/cart').json()['count'],0)
        self.assertEqual(self.client.delete('/api/account/addresses/'+str(self.address(1))).status_code,404)

    def test_checkout_money_idempotency_and_exactly_once_refund(self):
        self.add();payload=self.body(payment_method='ShopeePay',voucher_code='SHOPEEAI20',use_coins=True)
        quote=self.client.post('/api/checkout/quote',json=payload)
        self.assertEqual(quote.status_code,200,quote.text);bill=quote.json()
        self.assertEqual(bill['total'],bill['subtotal']+bill['shipping_fee']-bill['shipping_discount']-bill['voucher_discount']-bill['coin_discount'])
        self.assertEqual(bill['coin_discount'],25000)
        self.assertEqual(bill['voucher_discount'],100000)
        first=self.client.post('/api/orders',json=payload)
        self.assertEqual(first.status_code,201,first.text);order=first.json()
        again=self.client.post('/api/orders',json=payload)
        self.assertEqual(again.json()['id'],order['id'])
        me=self.client.get('/api/auth/me').json()['user']
        self.assertEqual(me['wallet_balance'],2500000-bill['total']);self.assertEqual(me['shopee_coins'],60000)
        self.assertEqual(self.client.get('/api/products/1').json()['stock'],99)
        self.assertEqual(self.client.get('/api/cart').json()['count'],0)
        self.assertEqual(self.client.post('/api/orders',json={**payload,'use_coins':False}).status_code,409)
        for _ in range(2):
            self.assertEqual(self.client.post(f"/api/orders/{order['id']}/cancel").status_code,200)
        me=self.client.get('/api/auth/me').json()['user']
        self.assertEqual(me['wallet_balance'],2500000);self.assertEqual(me['shopee_coins'],85000)
        self.assertEqual(self.client.get('/api/products/1').json()['stock'],100)
        vouchers=self.client.get('/api/vouchers').json();self.assertEqual(next(v['status'] for v in vouchers if v['code']=='SHOPEEAI20'),'available')

    def test_checkout_insufficient_wallet_rolls_back(self):
        self.add()
        with connection(write=True) as db:
            db.execute('UPDATE users SET wallet_balance=1 WHERE id=1')
        result=self.client.post('/api/orders',json=self.body(payment_method='ShopeePay',use_coins=True,voucher_code='SHOPEEAI20'))
        self.assertEqual(result.status_code,409,result.text)
        self.assertEqual(len(self.client.get('/api/orders').json()),0)
        self.assertEqual(self.client.get('/api/auth/me').json()['user']['shopee_coins'],85000)
        self.assertEqual(self.client.get('/api/products/1').json()['stock'],100)
        self.assertEqual(self.client.get('/api/cart').json()['count'],1)

    def test_invalid_voucher_or_foreign_address_cannot_charge(self):
        self.add()
        self.assertEqual(self.client.post('/api/orders',json=self.body(voucher_code='NOTREAL')).status_code,400)
        self.assertEqual(self.client.post('/api/orders',json=self.body(address_id=self.address(2))).status_code,422)
        self.assertEqual(self.client.get('/api/cart').json()['count'],1)

    def test_changed_quote_is_not_charged_without_review(self):
        self.add()
        payload=self.body(payment_method='ShopeePay')
        bill=self.client.post('/api/checkout/quote',json=payload).json()
        with connection(write=True) as db:
            old_price=db.execute('SELECT price FROM products WHERE id=1').fetchone()[0]
            db.execute('UPDATE products SET price=price+1000 WHERE id=1')
        try:
            result=self.client.post('/api/orders',json={**payload,'expected_total':bill['total']})
            self.assertEqual(result.status_code,409,result.text)
            self.assertEqual(self.client.get('/api/auth/me').json()['user']['wallet_balance'],2500000)
            self.assertEqual(self.client.get('/api/cart').json()['count'],1)
        finally:
            with connection(write=True) as db:
                db.execute('UPDATE products SET price=? WHERE id=1',(old_price,))

    def test_concurrent_last_item_has_only_one_winner(self):
        self.add()
        other=TestClient(app);self.login(2,other);self.add(client=other)
        with connection(write=True) as db:
            db.execute('UPDATE products SET stock=1 WHERE id=1')
        payloads=[(self.client,self.body()),(other,self.body(client=other,address_id=self.address(2),idempotency_key='test-second-user-0001'))]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda pair:pair[0].post('/api/orders',json=pair[1]),payloads))
        self.assertEqual(sorted(r.status_code for r in responses),[201,409])
        self.assertEqual(self.client.get('/api/products/1').json()['stock'],0)
        with connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
        other.close()

    def test_address_default_invariant(self):
        for i in range(2):
            result=self.client.post('/api/account/addresses',json={'recipient_name':'Người nhận thử','phone':'0912345678','province_id':34,'detail':'123 Đường thử nghiệm, Phường 1','is_default':True})
            self.assertEqual(result.status_code,201,result.text)
        rows=self.client.get('/api/account/addresses').json()
        self.assertEqual(sum(a['is_default'] for a in rows),1)
        self.client.delete('/api/account/addresses/'+str(next(a['id'] for a in rows if a['is_default'])))
        rows=self.client.get('/api/account/addresses').json();self.assertEqual(sum(a['is_default'] for a in rows),1)

    def test_review_requires_delivery_and_is_unique(self):
        review={'rating':5,'content':'Sản phẩm tốt, giao hàng đúng mô phỏng.'}
        self.assertEqual(self.client.post('/api/products/1/reviews',json=review).status_code,403)
        self.add();order=self.client.post('/api/orders',json=self.body()).json()
        for _ in range(2):
            self.assertEqual(self.client.post(f"/api/orders/{order['id']}/demo-advance").status_code,200)
        self.assertEqual(self.client.post('/api/products/1/reviews',json=review).status_code,201)
        self.assertEqual(self.client.post('/api/products/1/reviews',json=review).status_code,409)
        self.assertEqual(self.client.post(f"/api/orders/{order['id']}/cancel").status_code,409)
        self.assertEqual(len(self.client.get('/api/products/1').json()['reviews']),1)

    def test_actual_muse_and_interaction_changes_scores(self):
        self.assertIsNotNone(service.model,service.error)
        before=self.client.get('/api/recommendations?limit=60').json()
        self.assertEqual(before['meta']['engine'],'Alibaba MUSE')
        self.assertEqual(before['meta']['history_length'],1000)
        self.assertTrue(all(0<=p['p_click']<=1 for p in before['items']))
        raw=list(service.model.items)[:8]
        scores_before,_=service.model.predict(1,raw)
        self.client.post('/api/recommendations/behavior/1')
        scores_after,_=service.model.predict(1,raw)
        self.assertNotEqual(scores_before,scores_after)
        similar=self.client.get('/api/recommendations?touchpoint=similar&product_id=1&limit=4').json()
        self.assertEqual(similar['meta']['score_type'],'cosine_similarity')
        self.assertTrue(all(p['id']!=1 and -1.001<=p['similarity']<=1.001 for p in similar['items']))
        history=self.client.get('/api/recommendations/history?limit=1000').json()
        self.assertIsInstance(history[0]['raw_item_id'],str)
        self.assertEqual(history[0]['action_type'],'click')

    def test_professor_demo_interest_makes_recommendation_change_visible(self):
        before=self.client.get('/api/recommendations?limit=24').json()
        self.assertIsNone(self.client.get('/api/recommendations/demo-state').json()['active_interest'])
        result=self.client.post('/api/recommendations/demo-interest/7')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['active_interest']['category_id'],7)

        after=self.client.get('/api/recommendations?limit=24').json()
        self.assertEqual(after['meta']['active_interest']['category_id'],7)
        self.assertNotEqual([p['id'] for p in before['items'][:12]],[p['id'] for p in after['items'][:12]])
        self.assertEqual(after['items'][0]['category_id'],7)
        category_name=after['meta']['active_interest']['category_name']
        self.assertTrue(all(category_name in p['recommendation_reason'] for p in after['items'] if p['category_id']==7))
        self.assertTrue(after['meta']['intent_summary'])

        history=self.client.get('/api/recommendations/history?limit=10').json()
        self.assertEqual(history[0]['action_type'],'demo_interest')
        self.assertEqual(self.client.delete('/api/recommendations/demo-interest').status_code,200)
        self.assertIsNone(self.client.get('/api/recommendations/demo-state').json()['active_interest'])

    def test_wishlist_and_notifications(self):
        self.assertTrue(self.client.put('/api/account/wishlist/1').json()['saved'])
        self.assertEqual(len(self.client.get('/api/account/wishlist').json()),1)
        self.login(2);self.assertEqual(self.client.get('/api/account/wishlist').json(),[])
        self.client.post('/api/account/notifications/read')
        self.assertTrue(all(n['is_read'] for n in self.client.get('/api/account/notifications').json()))

    def test_registration_password_reset_and_session_invalidation(self):
        email='customer-'+Path(tempfile.mktemp()).name+'@example.test'
        payload={'full_name':'Khách hàng mới','email':email,'phone':'0912345678','password':'A-strong-password'}
        result=self.client.post('/api/auth/register',json=payload)
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(result.json()['user']['wallet_balance'],0)
        self.assertEqual(result.json()['user']['shopee_coins'],0)
        self.assertNotIn('password_hash',result.json()['user'])
        self.assertIn('HttpOnly',result.headers['set-cookie'])
        challenge=self.client.post('/api/auth/forgot-password',json={'email':email}).json()['challenge_id']
        self.assertEqual(self.client.post('/api/auth/reset-password',json={'challenge_id':challenge,'code':'888999','password':'Another-strong-pass'}).status_code,200)
        self.assertIsNone(self.client.get('/api/auth/me').json()['user'])
        self.assertEqual(self.client.post('/api/auth/reset-password',json={'challenge_id':challenge,'code':'888999','password':'Another-strong-pass'}).status_code,400)
        self.assertEqual(self.client.post('/api/auth/login',json={'email':email,'password':'Another-strong-pass'}).status_code,200)
        with connection() as db:
            self.assertTrue(db.execute('SELECT password_hash FROM users WHERE email=?',(email,)).fetchone()[0].startswith('pbkdf2_sha256$600000$'))

    def test_reset_locks_after_five_incorrect_attempts(self):
        with connection() as db:
            email=db.execute('SELECT email FROM users WHERE id=1').fetchone()[0]
        challenge=self.client.post('/api/auth/forgot-password',json={'email':email}).json()['challenge_id']
        for _ in range(5):
            self.assertEqual(self.client.post('/api/auth/reset-password',json={'challenge_id':challenge,'code':'000000','password':'New-password-123'}).status_code,400)
        self.assertEqual(self.client.post('/api/auth/reset-password',json={'challenge_id':challenge,'code':'888999','password':'New-password-123'}).status_code,400)

    def test_production_disables_demo_capabilities(self):
        old=config.DEMO_MODE
        try:
            config.DEMO_MODE=False
            self.assertEqual(self.client.post('/api/auth/demo-login',json={'user_id':2}).status_code,404)
            self.assertEqual(self.client.get('/api/recommendations/debug').status_code,404)
            self.assertEqual(self.client.get('/api/recommendations/history').status_code,404)
            self.assertEqual(self.client.get('/api/recommendations/demo-state').status_code,404)
            self.assertEqual(self.client.post('/api/recommendations/demo-interest/7').status_code,404)
            self.assertEqual(self.client.delete('/api/recommendations/demo-interest').status_code,404)
            self.assertEqual(self.client.post('/api/auth/forgot-password',json={'email':'someone@example.test'}).status_code,503)
            me=self.client.get('/api/auth/me').json()
            self.assertFalse(me['demo_mode']);self.assertNotIn('raw_user_id',me['user'])
            self.add()
            self.assertEqual(self.client.post('/api/checkout/quote',json=self.body(payment_method='ShopeePay')).status_code,503)
        finally:
            config.DEMO_MODE=old

    def test_profile_validation_and_available_avatars(self):
        options=self.client.get('/api/account/avatar-options').json()
        self.assertEqual(len(options),8)
        body={'full_name':'Tên hiển thị','phone':'0912345678','gender':'Khác','birth_year':2000,'avatar_url':options[0]['url']}
        self.assertEqual(self.client.put('/api/account/profile',json=body).status_code,200)
        self.assertEqual(self.client.put('/api/account/profile',json={**body,'full_name':'  '}).status_code,422)
        self.assertEqual(self.client.put('/api/account/profile',json={**body,'avatar_url':'https://evil.example/image.svg'}).status_code,422)

    def test_buy_now_only_purchases_requested_item_and_preserves_cart(self):
        self.add(1,2);self.add(2,3)
        cart_before=self.client.get('/api/cart').json()['items']
        payload=self.body(buy_now={'product_id':2,'quantity':1})
        result=self.client.post('/api/orders',json=payload)
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual([(i['product_id'],i['quantity']) for i in result.json()['items']],[(2,1)])
        cart_after=self.client.get('/api/cart').json()['items']
        fields=lambda rows:[(i['id'],i['quantity'],i['is_selected']) for i in rows]
        self.assertEqual(fields(cart_before),fields(cart_after))
        self.assertEqual(self.client.get('/api/products/1').json()['stock'],100)
        self.assertEqual(self.client.get('/api/products/2').json()['stock'],99)
        self.assertEqual(self.client.post('/api/orders',json=payload).json()['id'],result.json()['id'])

    def test_buy_now_works_without_cart_and_checks_stock(self):
        body=self.body(buy_now={'product_id':1,'quantity':2})
        self.assertEqual(self.client.post('/api/orders',json=body).status_code,201)
        self.assertEqual(self.client.get('/api/cart').json()['count'],0)
        body=self.body(buy_now={'product_id':1,'quantity':99},idempotency_key='test-direct-stock-0001')
        self.assertEqual(self.client.post('/api/orders',json=body).status_code,409)

    def test_same_total_different_items_or_address_requires_new_quote(self):
        with connection(write=True) as db:
            db.execute('UPDATE products SET price=200000,is_freeship=1 WHERE id IN (1,2)')
        self.add(1);payload=self.body()
        item=self.client.get('/api/cart').json()['items'][0]
        self.client.delete('/api/cart/'+str(item['cart_item_id']));self.add(2)
        self.assertEqual(self.client.post('/api/orders',json=payload).status_code,409)
        payload=self.body()
        with connection(write=True) as db:
            db.execute("UPDATE addresses SET detail=detail||' (đã cập nhật)' WHERE id=?",(self.address(),))
        self.assertEqual(self.client.post('/api/orders',json=payload).status_code,409)
        self.assertEqual(self.client.get('/api/orders').json(),[])
        missing={k:v for k,v in payload.items() if k!='quote_token'}
        self.assertEqual(self.client.post('/api/orders',json=missing).status_code,422)

    def test_shipping_threshold_is_per_shop_and_shared_with_cart(self):
        with connection(write=True) as db:
            db.execute('UPDATE products SET price=80000,is_freeship=1 WHERE id IN (1,2)')
        self.add(1);self.add(2)
        quote=self.client.post('/api/checkout/quote',json={'address_id':self.address()}).json()
        self.assertEqual(quote['subtotal'],160000)
        self.assertEqual(quote['shipping_discount'],0)
        self.assertEqual([g['remaining'] for g in quote['shipping_groups']],[70000,70000])
        cart=self.client.get('/api/cart').json()
        self.assertEqual([g['remaining'] for g in cart['shipping_groups']],[70000,70000])
        self.add(1)
        quote=self.client.post('/api/checkout/quote',json={'address_id':self.address()}).json()
        self.assertEqual(quote['shipping_discount'],quote['shipping_fee']//2)
        with connection(write=True) as db:
            db.execute('UPDATE products SET is_freeship=0 WHERE id=2')
        quote=self.client.post('/api/checkout/quote',json={'address_id':self.address()}).json()
        self.assertEqual(quote['shipping_discount'],quote['shipping_fee']//2)

    def test_shipping_voucher_without_benefit_is_not_consumed(self):
        self.add(1)
        self.client.post('/api/vouchers/1/claim')
        bill=self.client.post('/api/checkout/quote',json={'address_id':self.address()}).json()
        option=next(v for v in bill['available_vouchers'] if v['code']=='FREESHIP50K')
        self.assertFalse(option['eligible'])
        payload=self.body(voucher_code='FREESHIP50K')
        self.assertEqual(self.client.post('/api/orders',json=payload).status_code,400)
        self.assertEqual(self.client.get('/api/orders').json(),[])
        self.assertEqual(next(v['status'] for v in self.client.get('/api/vouchers').json() if v['code']=='FREESHIP50K'),'available')

    def test_unavailable_cart_rows_can_be_deselected_and_bulk_selection_skips_them(self):
        self.add(1);self.add(2)
        with connection(write=True) as db:
            db.execute('UPDATE products SET stock=0 WHERE id=1')
        item=next(i for i in self.client.get('/api/cart').json()['items'] if i['id']==1)
        self.assertEqual(self.client.put('/api/cart/'+str(item['cart_item_id']),json={'quantity':1,'is_selected':False}).status_code,200)
        self.assertEqual(self.client.put('/api/cart/selection',json={'is_selected':True}).status_code,200)
        items=self.client.get('/api/cart').json()['items']
        self.assertEqual({i['id']:i['is_selected'] for i in items},{1:0,2:1})
        self.assertEqual(self.client.post('/api/orders',json=self.body()).status_code,201)

    def test_reorder_is_atomic_and_owner_only(self):
        self.add(1);self.add(2)
        order=self.client.post('/api/orders',json=self.body()).json()
        with connection(write=True) as db:
            db.execute('UPDATE products SET stock=0 WHERE id=2')
        result=self.client.post(f"/api/orders/{order['id']}/reorder")
        self.assertEqual(result.status_code,409,result.text)
        self.assertEqual(self.client.get('/api/cart').json()['count'],0)
        self.login(2)
        self.assertEqual(self.client.post(f"/api/orders/{order['id']}/reorder").status_code,404)
        self.login(1)
        with connection(write=True) as db:
            db.execute('UPDATE products SET stock=5 WHERE id=2')
        self.assertEqual(self.client.post(f"/api/orders/{order['id']}/reorder").status_code,200)
        self.assertEqual(self.client.get('/api/cart').json()['count'],2)

    def test_recommendations_respect_context_and_have_stable_diverse_prefix(self):
        before=self.client.get('/api/recommendations?limit=12').json()
        expanded=self.client.get('/api/recommendations?limit=24').json()
        self.assertEqual([p['id'] for p in before['items']],[p['id'] for p in expanded['items'][:12]])
        self.assertTrue(before['items'])
        self.assertEqual(len({p['image_url'] for p in before['items']}),len(before['items']))
        target=self.client.get('/api/products/1').json()
        related=self.client.get('/api/recommendations?touchpoint=similar&product_id=1&limit=12').json()
        self.assertTrue(related['items'])
        self.assertTrue(all(p['category_id']==target['category_id'] and target['price']/2<=p['price']<=target['price']*2 for p in related['items']))
        self.assertEqual(self.client.get('/api/recommendations?touchpoint=similar&product_id=999999').status_code,404)
        self.assertEqual(self.client.get('/api/recommendations?touchpoint=cart').json()['items'],[])
        self.add(1);self.add(2)
        item=next(i for i in self.client.get('/api/cart').json()['items'] if i['id']==2)
        self.client.put('/api/cart/'+str(item['cart_item_id']),json={'quantity':1,'is_selected':False})
        recs=self.client.get('/api/recommendations?touchpoint=cart').json()
        self.assertTrue(recs['items'])
        allowed=set(recs['meta']['allowed_categories'])
        self.assertTrue(all(p['category_id'] in allowed and p['id'] not in (1,2) for p in recs['items']))
        self.assertEqual(len(recs['items']),len({p['image_url'] for p in recs['items']}))
        cart_photos={p['image_url'] for p in self.client.get('/api/cart').json()['items']}
        self.assertTrue(all(p['image_url'] not in cart_photos for p in recs['items']))
        self.assertTrue(all(p['price']<=recs['meta']['price_cap'] for p in recs['items']))
        with connection(write=True) as db:
            db.execute('UPDATE products SET price=1000 WHERE id=1')
            db.execute('UPDATE products SET price=10000000 WHERE category_id IN ('+
                       ','.join('?' for _ in allowed)+') AND id NOT IN (1,2)',tuple(allowed))
        self.assertEqual(self.client.get('/api/recommendations?touchpoint=cart').json()['items'],[])

    def test_new_customer_recommendations_and_missing_model_fallback(self):
        email='cold-'+Path(tempfile.mktemp()).name+'@example.test'
        response=self.client.post('/api/auth/register',json={'full_name':'Khách mới','email':email,'phone':'0912345678','password':'A-strong-password'})
        self.assertEqual(response.status_code,201,response.text)
        result=self.client.get('/api/recommendations').json()
        self.assertTrue(result['meta']['cold_start'])
        self.assertEqual(result['meta']['history_length'],0)
        self.assertTrue(all(0<=p['p_click']<=1 for p in result['items']))
        with patch.object(service,'model',None):
            fallback=self.client.get('/api/recommendations').json()
        self.assertTrue(fallback['items'])
        self.assertFalse(fallback['meta']['checkpoint_loaded'])
        self.assertTrue(all('p_click' not in p for p in fallback['items']))

    def test_inference_failure_falls_back_and_debug_is_scoped_to_user(self):
        service.last_metrics.clear()
        with patch.object(service.model,'predict',side_effect=RuntimeError('test inference failure')):
            with self.assertLogs(level='ERROR'):
                result=self.client.get('/api/recommendations').json()
        self.assertTrue(result['items'])
        self.assertFalse(result['meta']['model_used'])
        self.assertEqual(result['meta']['engine'],'Catalog fallback')
        self.assertTrue(all('p_click' not in p for p in result['items']))
        self.login(2)
        self.assertEqual(self.client.get('/api/recommendations/debug').json()['last_metrics'],{})
        self.login(1)
        self.assertEqual(self.client.get('/api/recommendations/debug').json()['last_metrics']['fallback_reason'],'inference_failed')

    def test_evaluation_uses_same_inference_as_web_without_writing_history(self):
        model=service.model
        source,hist,categories,_=model.history(1)
        raw=list(model.items)[:9]
        with connection() as db:
            count=db.execute('SELECT COUNT(*) FROM user_behavior_history').fetchone()[0]
        served,_=model.predict(1,raw)
        evaluated=model.predict_context(source,hist,categories,[model.items[x] for x in raw])
        for actual,expected in zip(evaluated,served):
            self.assertAlmostEqual(actual,expected,places=7)
        with connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM user_behavior_history').fetchone()[0],count)

    def test_personalized_search_paginates_beyond_candidate_window(self):
        expected=set()
        with connection() as db:
            total=db.execute('SELECT COUNT(*) FROM products WHERE stock>0').fetchone()[0]
            tail=[r[0] for r in db.execute('SELECT id FROM products WHERE stock>0 ORDER BY sold_count DESC,id LIMIT 24 OFFSET 120')]
        for page in range(1,7):
            result=self.client.get('/api/products',params={'sort':'relevance','page':page}).json()
            self.assertEqual(result['total'],total)
            self.assertEqual(len(result['items']),24)
            ids={p['id'] for p in result['items']}
            self.assertFalse(expected&ids)
            expected.update(ids)
            if page==6:
                self.assertEqual([p['id'] for p in result['items']],tail)
                self.assertFalse(result['personalized'])
        # A page may cross the 120-item boundary when a different page size is used.
        left=self.client.get('/api/products?sort=relevance&page_size=7&page=17').json()['items']
        boundary=self.client.get('/api/products?sort=relevance&page_size=7&page=18').json()['items']
        self.assertEqual(len(boundary),7)
        self.assertFalse({p['id'] for p in left}&{p['id'] for p in boundary})
        self.assertEqual(boundary[1]['id'],tail[0])
        last=self.client.get('/api/products',params={'sort':'relevance','page':(total+23)//24}).json()
        self.assertEqual(len(last['items']),total%24 or 24)

    def test_search_fallback_and_public_ai_source_are_truthful(self):
        result=self.client.get('/api/recommendations').json()
        self.assertTrue(result['meta']['model_used'])
        self.assertTrue(all(p['recommendation_source']=='ai' for p in result['items']))
        self.assertIsNone(result['quality'].get('catalog_accuracy_percent'))
        with patch.object(service.model,'predict',side_effect=RuntimeError('test failure')):
            with self.assertLogs(level='WARNING'):
                search=self.client.get('/api/products?sort=relevance&q=tai').json()
            with self.assertLogs(level='ERROR'):
                fallback=self.client.get('/api/recommendations').json()
        self.assertFalse(search['personalized'])
        self.assertTrue(all('p_click' not in p and 'recommendation_source' not in p for p in search['items']))
        self.assertFalse(fallback['quality']['available'])
        self.assertTrue(all(p['recommendation_source']=='catalog' for p in fallback['items']))
        # Selecting Popular explicitly must keep its documented sort order.
        popular=self.client.get('/api/products?q=tai&sort=popular').json()
        self.assertFalse(popular['personalized'])
        self.client.cookies.clear()
        guest=self.client.get('/api/recommendations').json()
        self.assertFalse(guest['meta']['model_used'])
        self.assertFalse(guest['quality']['available'])

    def test_favorite_contributes_to_recent_intent(self):
        with connection(write=True) as db:
            db.execute("DELETE FROM user_behavior_history WHERE user_id=1 AND action_type!='imported_click'")
        self.client.put('/api/account/wishlist/1')
        result=self.client.get('/api/recommendations').json()
        self.assertTrue(result['meta']['intent_summary'])
        self.assertEqual(result['meta']['intent_summary'][0]['category_id'],1)

    def test_complementary_recommendations_exclude_target_and_invalid_context(self):
        target=self.client.get('/api/products/1').json()
        for guest in (False,True):
            if guest:self.client.cookies.clear()
            response=self.client.get('/api/recommendations?touchpoint=complementary&product_id=1&limit=12')
            self.assertEqual(response.status_code,200,response.text)
            result=response.json()
            self.assertTrue(result['items'])
            self.assertTrue(result['meta']['model_used'])
            self.assertTrue(all(p['id']!=1 and p['stock']>0 and p['category_id'] in (1,2,8) for p in result['items']))
            self.assertTrue(all(not p['name'].lower().startswith(target['name'].split()[0].lower()) for p in result['items']))
            self.assertEqual(len(result['items']),len({p['image_url'] for p in result['items']}))
        self.assertEqual(self.client.get('/api/recommendations?touchpoint=complementary').status_code,422)
        self.assertEqual(self.client.get('/api/recommendations?touchpoint=complementary&product_id=999999').status_code,404)
        self.assertEqual(self.client.get('/api/recommendations?touchpoint=invalid').status_code,422)
        self.assertEqual(self.client.get('/api/recommendations?limit=0').status_code,422)

    def test_visible_feed_uses_coherent_titles_and_never_repeats_photos(self):
        from app.recommender.catalog import curated_demo_titles,product_kind
        result=self.client.get('/api/recommendations?limit=60').json()
        self.assertTrue(all(p['name'] in curated_demo_titles() for p in result['items']))
        self.assertEqual(len(result['items']),len({p['image_url'] for p in result['items']}))
        self.assertEqual(len(result['items']),len({p['name'] for p in result['items']}))
        target=self.client.get('/api/products/2').json()
        similar=self.client.get('/api/recommendations?touchpoint=similar&product_id=2&limit=12').json()
        self.assertTrue(similar['items'])
        self.assertTrue(similar['meta']['context_policy'].startswith('same_kind'))
        self.assertTrue(all(product_kind(p['name'])==product_kind(target['name']) for p in similar['items']))
        self.assertTrue(all(p['image_url']!=target['image_url'] for p in similar['items']))
        self.assertFalse(similar['quality']['available'])
        viewed=result['items'][0]['id']
        self.client.post('/api/recommendations/behavior/'+str(viewed))
        refreshed=self.client.get('/api/recommendations?limit=60').json()
        self.assertNotIn(viewed,[p['id'] for p in refreshed['items']])


if __name__=='__main__':
    unittest.main()
