import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.recommender import evaluation
from app.recommender.evaluation import roc_auc,click_metrics


class EvaluationTests(unittest.TestCase):
    def test_auc_accounts_for_ties_and_single_class(self):
        self.assertEqual(roc_auc([0,1],[.1,.9]),1)
        self.assertEqual(roc_auc([0,1],[.9,.1]),0)
        self.assertEqual(roc_auc([0,1],[.3,.3]),.5)
        self.assertAlmostEqual(roc_auc([0,0,1,1],[.1,.4,.35,.8]),.75)
        self.assertIsNone(roc_auc([1,1],[.2,.3]))

    def test_metrics_report_baseline_and_only_eligible_gauc_users(self):
        result=click_metrics([0,1,0,0],[.1,.9,.2,.3],['a','a','b','b'])
        self.assertEqual(result['auc'],1)
        self.assertEqual(result['gauc'],1)
        self.assertEqual(result['gauc_eligible_users'],1)
        self.assertEqual(result['gauc_eligible_impressions'],2)
        self.assertEqual(result['accuracy'],1)
        self.assertEqual(result['always_no_click_accuracy'],.75)
        self.assertIsNone(result['precision_at_10'])
        result=click_metrics([0,0,0,1],[.1,.1,.1,.1],['a']*4)
        self.assertEqual(result['accuracy'],.75)
        self.assertEqual(result['balanced_accuracy'],.5)
        self.assertEqual(result['recall'],0)

    def test_top10_excludes_short_candidate_groups_and_measures_lift(self):
        y=[1]*5+[0]*15+[1,0]
        p=[.9]*5+[.1]*15+[.9,.1]
        result=click_metrics(y,p,['large']*20+['small']*2)
        self.assertEqual(result['precision_at_10_eligible_users'],1)
        self.assertEqual(result['precision_at_10'],.5)
        self.assertEqual(result['precision_at_10_random_baseline'],.25)
        self.assertEqual(result['precision_at_10_lift'],2)

    def test_invalid_predictions_are_rejected(self):
        for labels,scores,users in [([],[],[]),([1],[.2,.3],['a']),([2],[.1],['a']),([1],[float('nan')],['a']),([0],[1.1],['a'])]:
            with self.assertRaises(ValueError):click_metrics(labels,scores,users)

    def test_public_summary_rejects_stale_artifacts_and_does_not_claim_catalog_accuracy(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'report.json'
            data={'schema_version':2,'run_status':'completed','checkpoint_sha256':{'dense':'hash'},
                  'predictions_sha256':'predictions','artifacts':{'dense':123},'serving_sha256':'current',
                  'evaluated_at':'2026-10-15T00:00:00+00:00','metrics':{'auc':.64,'sample_size':1000,'users':20,'positives':200,'negatives':800},
                  'sampling':{'shards':[{'rows':1000,'offset':0,'row_group':0}]}}
            report.write_text(json.dumps(data))
            with patch.object(evaluation,'REPORT_PATH',report),patch.object(evaluation,'artifact_signature',return_value={'dense':123}),patch.object(evaluation,'serving_signature',return_value='current'):
                evaluation._read_report.cache_clear()
                summary=evaluation.evaluation_summary()
                self.assertTrue(summary['available'])
                self.assertEqual(summary['pairwise_ranking_percent'],64)
                self.assertIsNone(summary['catalog_accuracy_percent'])
                with patch.object(evaluation,'serving_signature',return_value='changed'):
                    self.assertFalse(evaluation.evaluation_summary()['available'])
                with patch.object(evaluation,'artifact_signature',return_value={'dense':456}):
                    self.assertFalse(evaluation.evaluation_summary()['available'])
        evaluation._read_report.cache_clear()
