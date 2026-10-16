"""Original-data ranking, cache invalidation and provenance on an isolated DB."""
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
from app.native_catalog import MODE, catalog_info
from app.recommender.service import service
from scripts.migrate_taobao import migrate, repair_orphans
from scripts.expand_taobao_catalog import expand,TARGET


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = config.DB_PATH
        cls.tmp = tempfile.TemporaryDirectory()
        target = Path(cls.tmp.name)/'native.db'
        with sqlite3.connect(cls.original) as src, sqlite3.connect(target) as dest:
            src.backup(dest)
        config.DB_PATH = target
        initialize()
        migrate(); cls.info = expand()
        cls.ctx = TestClient(app); cls.client = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None,None,None); config.DB_PATH=cls.original; cls.tmp.cleanup()

    def setUp(self):
        self.client.post('/api/auth/demo-login',json={'user_id':1})

    def test_original_features_and_no_fabricated_metadata(self):
        result=self.client.get('/api/catalog').json()
        self.assertEqual(result['source']['mode'],MODE)
        self.assertEqual(result['source']['original_features_verified'],TARGET)
        if 'original_profiles_verified' in result['source']:
            self.assertEqual(result['source']['original_profiles_verified'],8)
        self.assertEqual(len(result['categories']),result['source']['group_count'])
        self.assertGreater(result['source']['group_count'],1200)
        self.assertTrue(all(c['id']>=10001 for c in result['categories']))
        with connection() as db:
            for row in db.execute('SELECT p.*,m.features_json FROM products p JOIN muse_item_features m ON m.raw_item_id=p.raw_item_id'):
                self.assertEqual(row['source_category_id'],str(json.loads(row['features_json'])['206']))
                self.assertTrue(row['name'].startswith('Mẫu TB-'))
                self.assertEqual(row['image_url'],f'/api/item-art/{row["id"]}.svg')
                if not row['source_feature_complete']:
                    self.assertEqual(row['stock'],0)
        self.assertEqual(migrate()['mode'],MODE)
        self.assertEqual(expand()['product_count'],TARGET)  # Migration is safe to repeat.

    def test_checkpoint_order_all_profiles_and_stable_prefix(self):
        for uid in range(1,9):
            self.client.post('/api/auth/demo-login',json={'user_id':uid})
            result=self.client.get('/api/recommendations?limit=24').json()
            self.assertTrue(result['meta']['model_used'],result)
            self.assertEqual(result['meta']['scored_catalog_count'],TARGET)
            self.assertEqual(result['meta']['history_length'],1000)
            self.assertEqual(result['meta']['ranking_policy'],'checkpoint_score_desc')
            scores=[p['p_click'] for p in result['items']]
            self.assertEqual(scores,sorted(scores,reverse=True))
            larger=self.client.get('/api/recommendations?limit=60').json()
            self.assertTrue(larger['meta']['ranking_cache_hit'])
            self.assertEqual(result['items'],larger['items'][:24])
            expected,_=service.model.predict(uid,[int(p['raw_item_id']) for p in result['items'][:4]])
            for actual,score in zip(scores,expected):
                self.assertAlmostEqual(actual,score,places=6)

    def test_group_filter_does_not_fabricate_history(self):
        group=self.client.get('/api/catalog').json()['categories'][0]['id']
        with connection() as db:
            before=db.execute('SELECT COUNT(*) FROM user_behavior_history').fetchone()[0]
        result=self.client.get(f'/api/recommendations?limit=60&category_id={group}').json()
        self.assertGreater(len(result['items']),1)
        self.assertTrue(all(p['category_id']==group for p in result['items']))
        scores=[p['p_click'] for p in result['items']]
        self.assertEqual(scores,sorted(scores,reverse=True))
        self.assertEqual(self.client.post(f'/api/recommendations/demo-interest/{group}').status_code,409)
        with connection() as db:
            self.assertEqual(before,db.execute('SELECT COUNT(*) FROM user_behavior_history').fetchone()[0])

    def test_action_invalidates_scores_and_raw_sequence_pairs_stay_original(self):
        before=self.client.get('/api/recommendations?limit=60').json()
        p=before['items'][0]
        with connection() as db:
            original=db.execute('SELECT features_json FROM muse_user_features WHERE user_id=1').fetchone()[0]
        self.assertEqual(self.client.post(f'/api/recommendations/behavior/{p["id"]}').status_code,200)
        after=self.client.get('/api/recommendations?limit=60').json()
        self.assertFalse(after['meta']['ranking_cache_hit'])
        self.assertNotEqual({p['id']:p['p_click'] for p in before['items']},
                            {p['id']:p['p_click'] for p in after['items']})
        with connection() as db:
            self.assertEqual(original,db.execute('SELECT features_json FROM muse_user_features WHERE user_id=1').fetchone()[0])

    def test_search_uses_complete_catalog_ranking_and_int64_ids(self):
        a=self.client.get('/api/products?sort=relevance&page=1&page_size=60').json()
        b=self.client.get('/api/products?sort=relevance&page=2&page_size=60').json()
        self.assertEqual(a['total'],TARGET)
        self.assertFalse({p['id'] for p in a['items']}&{p['id'] for p in b['items']})
        scores=[p['p_click'] for p in a['items']+b['items']]
        self.assertEqual(scores,sorted(scores,reverse=True))
        self.assertTrue(all(isinstance(p['raw_item_id'],str) for p in a['items']))
        self.assertEqual(len(self.client.get('/api/products?sort=relevance&page=6').json()['items']),24)
        search=self.client.get('/api/products',params={'q':'Nhóm 001'}).json()
        self.assertGreater(search['total'],0)
        self.assertTrue(all(p.get('original_category_name',p['category_name'])=='Nhóm 001' for p in search['items']))

    def test_similar_cart_and_explicit_fallback(self):
        result=self.client.get('/api/recommendations').json(); pid=result['items'][0]['id']
        similar=self.client.get(f'/api/recommendations?touchpoint=similar&product_id={pid}').json()
        scores=[p['similarity'] for p in similar['items']]
        self.assertEqual(scores,sorted(scores,reverse=True))
        self.assertTrue(all(p['id']!=pid for p in similar['items']))
        self.assertFalse(similar['quality']['available'])
        import numpy as np
        with patch.object(service.model,'indices',return_value=np.array([0])):
            missing_scl=self.client.get(f'/api/recommendations?touchpoint=similar&product_id={pid}').json()
        self.assertFalse(missing_scl['meta']['model_used'])
        self.assertEqual(missing_scl['meta']['fallback_reason'],'target_scl_unavailable')
        self.client.post('/api/cart',json={'product_id':pid,'quantity':1})
        cart=self.client.get('/api/recommendations?touchpoint=cart').json()
        self.assertTrue(all(p['id']!=pid for p in cart['items']))
        with patch.object(service,'model',None):
            fallback=self.client.get('/api/recommendations').json()
        self.assertFalse(fallback['meta']['model_used'])
        self.assertTrue(fallback['items'])
        self.assertTrue(all('p_click' not in p and p['recommendation_source']=='catalog' for p in fallback['items']))

    def test_anonymous_art_has_correct_content_type_and_valid_item(self):
        art=self.client.get('/api/item-art/1.svg')
        self.assertEqual(art.status_code,200)
        self.assertIn('image/svg+xml',art.headers['content-type'])
        self.assertIn('TB / 00001',art.text)
        self.assertEqual(self.client.get('/api/item-art/999999999.svg').status_code,404)

    def test_experience_reports_original_groups_and_real_activity_only(self):
        from collections import Counter
        with connection() as db:
            source=json.loads(db.execute('SELECT features_json FROM muse_user_features WHERE user_id=1').fetchone()[0])
            before=db.execute('SELECT COUNT(*) FROM user_behavior_history').fetchone()[0]
        data=self.client.get('/api/recommendations/experience').json()
        self.assertTrue(data['imported']);self.assertEqual(data['original_events'],1000)
        self.assertTrue(data['history_examples'])
        self.assertTrue(all(int(p['raw_item_id']) in source['150_2_180'] for p in data['history_examples']))
        counts=Counter(source['151_2_180'])
        for group in data['top_groups']:
            with connection() as db:
                raw=int(db.execute('SELECT source_category_id FROM products WHERE category_id=? LIMIT 1',(group['id'],)).fetchone()[0])
            self.assertEqual(group['events'],counts[raw]);self.assertGreater(group['available_count'],0)
        with connection() as db:
            self.assertEqual(before,db.execute('SELECT COUNT(*) FROM user_behavior_history').fetchone()[0])
        pid=self.client.get('/api/recommendations').json()['items'][0]['id']
        self.client.post(f'/api/recommendations/behavior/{pid}')
        updated=self.client.get('/api/recommendations/experience').json()
        self.assertEqual(updated['recent'][0]['id'],pid)
        self.assertEqual(updated['recent'][0]['action_type'],'click')
        self.assertEqual(updated['live_events'],data['live_events']+1)
        self.client.post('/api/auth/logout')
        guest=self.client.get('/api/recommendations/experience').json()
        self.assertEqual(guest['recent'],[]);self.assertEqual(guest['history_examples'],[])
        self.assertEqual(guest['original_events'],0)

    def test_home_hides_seen_items_without_overriding_model_scores(self):
        result=self.client.get('/api/recommendations?limit=60').json()
        with connection() as db:
            source=json.loads(db.execute('SELECT features_json FROM muse_user_features WHERE user_id=1').fetchone()[0])
            seen=set(source['150_2_180'])
            seen.update(r[0] for r in db.execute("SELECT raw_item_id FROM user_behavior_history WHERE user_id=1 AND action_type IN ('click','favorite','add_to_cart','purchase')"))
        self.assertTrue(all(int(p['raw_item_id']) not in seen for p in result['items']))
        self.assertEqual(result['meta']['discovery_policy'],'hide_seen_items')
        self.assertEqual(result['meta']['scored_catalog_count'],TARGET)
        ids=[int(p['raw_item_id']) for p in result['items']]
        self.assertTrue((service.model.indices(service.model.maps['150_2_180'],ids)>0).all())
        self.assertTrue((service.model.indices(service.model.scl_keys,ids)>0).all())
        from collections import Counter
        groups=Counter(source['151_2_180'])
        self.assertTrue(all(p['history_group_events']==groups[int(p['source_category_id'])] for p in result['items']))

    def test_comparison_is_read_only_and_limited_to_imported_demo_profiles(self):
        with connection() as db:
            history=db.execute('SELECT COUNT(*) FROM user_behavior_history').fetchone()[0]
            logs=db.execute('SELECT COUNT(*) FROM recommendation_logs').fetchone()[0]
        result=self.client.get('/api/recommendations/compare-profiles?left=1&right=2')
        self.assertEqual(result.status_code,200,result.text)
        data=result.json();self.assertTrue(data['read_only'])
        self.assertTrue(data['left']['model_used'] and data['right']['model_used'])
        self.assertEqual(data['shared_items'],len({p['id'] for p in data['left']['items']}&{p['id'] for p in data['right']['items']}))
        self.assertEqual(data['left']['profile']['id'],1);self.assertEqual(data['right']['profile']['id'],2)
        self.assertNotEqual([p['id'] for p in data['left']['items']],[p['id'] for p in data['right']['items']])
        with connection() as db:
            self.assertEqual(history,db.execute('SELECT COUNT(*) FROM user_behavior_history').fetchone()[0])
            self.assertEqual(logs,db.execute('SELECT COUNT(*) FROM recommendation_logs').fetchone()[0])
        self.assertEqual(self.client.get('/api/recommendations/compare-profiles?left=1&right=1').status_code,422)
        self.assertEqual(self.client.get('/api/recommendations/compare-profiles?left=1&right=99999').status_code,404)
        with patch.object(config,'DEMO_MODE',False):
            self.assertEqual(self.client.get('/api/recommendations/compare-profiles').status_code,404)

    def test_new_user_does_not_borrow_a_profile(self):
        result=self.client.post('/api/auth/register',json={'full_name':'Khách mới Taobao','phone':'0912345678',
            'email':'native-new@example.test','password':'Taobao-test-2026!'})
        self.assertEqual(result.status_code,201,result.text)
        rec=self.client.get('/api/recommendations').json()
        self.assertTrue(rec['meta']['cold_start'])
        self.assertEqual(rec['meta']['history_length'],0)
        self.assertIsNone(self.client.get('/api/auth/me').json()['user']['raw_user_id'])
        pid=rec['items'][0]['id']
        self.client.post(f'/api/recommendations/behavior/{pid}')
        summary=self.client.get('/api/recommendations/experience').json()
        self.assertFalse(summary['imported']);self.assertEqual(summary['original_events'],0)
        self.assertEqual(summary['live_events'],1);self.assertEqual(summary['group_evidence_source'],'live')
        self.assertEqual(summary['top_groups'][0]['events'],1)


class OrphanRepairTests(unittest.TestCase):
    def test_removes_only_rows_without_an_existing_user(self):
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)')
        db.execute('INSERT INTO users VALUES (1)')
        for table in ('sessions','recommendation_logs','notifications'):
            db.execute(f'CREATE TABLE {table}(user_id INTEGER)')
            db.executemany(f'INSERT INTO {table} VALUES (?)',[(1,),(999,)])
        self.assertEqual(repair_orphans(db),{'sessions':1,'recommendation_logs':1,'notifications':1})
        self.assertEqual(repair_orphans(db),{})
        for table in ('sessions','recommendation_logs','notifications'):
            self.assertEqual(db.execute(f'SELECT user_id FROM {table}').fetchall(),[(1,)])
        db.close()
