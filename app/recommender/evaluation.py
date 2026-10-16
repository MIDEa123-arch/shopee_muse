"""Exact offline click metrics and a provenance-checked public evaluation summary."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from app import config

REPORT_PATH=config.ROOT/'docs/recommendation_evaluation.json'


def artifact_signature():
    files=[config.CHECKPOINT_DIR/name for name in
           ('muse_full_training_dense.ckpt','muse_full_training_sparse.ckpt')]
    files+=sorted((config.DATASET_DIR/'feature_map').glob('*.npy'))
    return {str(path.relative_to(path.parent)): {'bytes':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns}
            for path in files}


def serving_signature():
    root=Path(__file__).parent
    digest=hashlib.sha256()
    for path in [root/'model.py',*sorted((root/'upstream').glob('*.py'))]:
        digest.update(path.name.encode());digest.update(path.read_bytes())
    return digest.hexdigest()


def roc_auc(labels,scores):
    """Mann–Whitney AUC, with half credit for ties; undefined for a single class."""
    labels=np.asarray(labels,dtype=np.int8);scores=np.asarray(scores,dtype=np.float64)
    positives=int(labels.sum());negatives=len(labels)-positives
    if not positives or not negatives:
        return None
    order=np.argsort(scores,kind='stable');ordered=scores[order]
    starts=np.r_[0,np.flatnonzero(np.diff(ordered))+1];ends=np.r_[starts[1:],len(scores)]
    ranks=np.repeat((starts+1+ends)/2,ends-starts)
    return float((ranks[labels[order]==1].sum()-positives*(positives+1)/2)/(positives*negatives))


def click_metrics(labels,scores,user_ids):
    labels=np.asarray(labels,dtype=np.int8);scores=np.asarray(scores,dtype=np.float64)
    if not len(labels) or len(labels)!=len(scores) or len(labels)!=len(user_ids):
        raise ValueError('Labels, scores and users must be nonempty and aligned')
    if not np.isin(labels,[0,1]).all() or not np.isfinite(scores).all() or ((scores<0)|(scores>1)).any():
        raise ValueError('Invalid labels or prediction probabilities')
    predicted=scores>=.5;positive=labels==1
    tp=int((predicted&positive).sum());fp=int((predicted&~positive).sum())
    fn=int((~predicted&positive).sum());tn=int((~predicted&~positive).sum())
    recall=tp/(tp+fn) if tp+fn else 0.;specificity=tn/(tn+fp) if tn+fp else 0.
    precision=tp/(tp+fp) if tp+fp else 0.
    p=np.clip(scores,1e-7,1-1e-7);rate=float(labels.mean())
    log_loss=float(-(labels*np.log(p)+(1-labels)*np.log1p(-p)).mean())
    base_p=np.clip(rate,1e-7,1-1e-7)
    groups={}
    for index,uid in enumerate(user_ids):groups.setdefault(uid,[]).append(index)
    weighted_auc=0.;eligible_impressions=0;eligible_users=0;top_clicks=0;top_slots=0;random_clicks=0.
    for indices in groups.values():
        y=labels[indices];s=scores[indices];auc=roc_auc(y,s)
        if auc is not None:
            weighted_auc+=auc*len(indices);eligible_impressions+=len(indices);eligible_users+=1
        # Short groups are excluded: returning all observed items would give trivial recall.
        if len(indices)>=20 and 0<y.sum()<len(y):
            top=np.argsort(-s,kind='stable')[:10]
            top_clicks+=int(y[top].sum());top_slots+=10;random_clicks+=10*float(y.mean())
    return {'sample_size':len(labels),'users':len(groups),'positives':int(positive.sum()),
            'negatives':int((~positive).sum()),'click_rate':rate,'auc':roc_auc(labels,scores),
            'gauc':weighted_auc/eligible_impressions if eligible_impressions else None,
            'gauc_eligible_users':eligible_users,'gauc_eligible_impressions':eligible_impressions,
            'log_loss':log_loss,'constant_ctr_log_loss':float(-(labels*np.log(base_p)+(1-labels)*np.log1p(-base_p)).mean()),
            'brier_score':float(((scores-labels)**2).mean()),'mean_predicted_click_rate':float(scores.mean()),
            'threshold':.5,'accuracy':(tp+tn)/len(labels),'always_no_click_accuracy':1-rate,
            'balanced_accuracy':(recall+specificity)/2,'precision':precision,'recall':recall,
            'f1':2*precision*recall/(precision+recall) if precision+recall else 0.,
            'confusion_matrix':{'tp':tp,'fp':fp,'tn':tn,'fn':fn},
            'precision_at_10':top_clicks/top_slots if top_slots else None,
            'precision_at_10_random_baseline':random_clicks/top_slots if top_slots else None,
            'precision_at_10_eligible_users':top_slots//10,
            'precision_at_10_lift':top_clicks/random_clicks if random_clicks else None}


@lru_cache(maxsize=1)
def _read_report(report_mtime,artifacts,serving):
    report=json.loads(REPORT_PATH.read_text())
    if report.get('schema_version')!=2 or report.get('run_status')!='completed' or report.get('artifacts')!=json.loads(artifacts) or report.get('serving_sha256')!=serving:
        return {'available':False,'reason':'evaluation_outdated'}
    metrics=report['metrics'];auc=metrics.get('auc')
    if (not report.get('checkpoint_sha256') or not report.get('predictions_sha256')
            or sum(s['rows'] for s in report['sampling']['shards'])!=metrics['sample_size']
            or metrics['positives']+metrics['negatives']!=metrics['sample_size']
            or not all('offset' in s and 'row_group' in s for s in report['sampling']['shards'])):
        return {'available':False,'reason':'incomplete_evaluation'}
    if auc is None or not 0<=auc<=1 or metrics.get('sample_size',0)<100:
        return {'available':False,'reason':'insufficient_evaluation'}
    return {'available':True,'evaluated_at':report['evaluated_at'],
            'sample_size':metrics['sample_size'],'users':metrics['users'],
            'pairwise_ranking_percent':round(auc*100,2),'scope':'sampled_taobao_test',
            'sampled_shards':len(report['sampling']['shards']),
            'measures':'click_ranking','catalog_accuracy_percent':None}


def evaluation_summary():
    try:
        return _read_report(REPORT_PATH.stat().st_mtime_ns,json.dumps(artifact_signature(),sort_keys=True),serving_signature())
    except (OSError,ValueError,KeyError,TypeError):
        return {'available':False,'reason':'evaluation_unavailable'}
