"""Commerce invariants and actual checkpoint integration, using an isolated DB copy.

Run: python -m unittest discover -s tests -v
Requires httpx; no mutations are made to the real customer database.
"""
import concurrent.futures
import json
import sqlite3
import tempfile
import unittest
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
        with sqlite3.connect(cls.original_db) as source,sqlite3.connect(config.DB_PATH) as target:
            source.backup(target)
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
            db.execute('UPDATE users SET wallet_balance=2500000,shopee_coins=85000 WHERE id IN (1,2)')
            db.execute("UPDATE user_vouchers SET status='available'")
        self.login(1)

    def login(self,uid,client=None):
        result=(client or self.client).post('/api/auth/demo-login',json={'user_id':uid})
        self.assertEqual(result.status_code,200,result.text)
        return result.json()['user']

    def address(self,uid=1):
        with connection() as db:
            return db.execute('SELECT id FROM addresses WHERE user_id=? ORDER BY is_default DESC LIMIT 1',(uid,)).fetchone()[0]

    def body(self,**kwargs):
        return {'address_id':self.address(),'payment_method':'COD','idempotency_key':'test-order-unique-0001',**kwargs}

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
        payloads=[(self.client,self.body()),(other,self.body(address_id=self.address(2),idempotency_key='test-second-user-0001'))]
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


if __name__=='__main__':
    unittest.main()
