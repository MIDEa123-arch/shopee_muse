"""Reproducible, read-only evaluation on held-out impressions across test shards.

Run: python scripts/evaluate_recommender.py --samples 2048 --shards 4
No training, demo metadata, injected user intent, or live web interactions enter this run.
This evaluates the shared checkpoint forward path, not end-to-end shop ranking quality.
"""
import argparse
import gc
import hashlib
import json
import mmap
import resource
import sys
import time
from collections import OrderedDict
from datetime import datetime,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
import pyarrow.parquet as pq

from app import config
from app.recommender.evaluation import artifact_signature,click_metrics,serving_signature,REPORT_PATH
from app.recommender.model import MuseModel,USER_FIELDS


def resident_mb():
    with open('/proc/self/statm') as stream:
        return int(stream.read().split()[1])*4096/1024**2


def release_evaluation_pages(model):
    # Keep evaluation memory bounded: these are read-only file-backed arrays.
    for array in [*model.maps.values(),model.scl_keys,model.scl_values]:
        if hasattr(array._mmap,'madvise') and hasattr(mmap,'MADV_DONTNEED'):
            array._mmap.madvise(mmap.MADV_DONTNEED)
    gc.collect()


def evaluate(samples=2048,shards=4,seed=20261015,output=REPORT_PATH):
    if samples<100 or shards<1 or samples<shards:
        raise ValueError('Use at least 100 samples and one sample per shard')
    files=sorted((config.DATASET_DIR/'test').glob('test-shard-*.parquet'))
    if not files:raise FileNotFoundError('No held-out test shards found')
    rng=np.random.default_rng(seed)
    chosen=sorted(rng.choice(len(files),size=min(shards,len(files)),replace=False).tolist())
    artifacts=artifact_signature();code_hash=serving_signature()
    print('Loading one CPU checkpoint instance; streaming evaluation in batches of 64.',flush=True)
    model=MuseModel();labels=[];scores=[];users=[];sampling=[];inference_seconds=0.;started=time.perf_counter()
    print(f'Model ready; RSS {resident_mb():.0f} MiB',flush=True)
    target_covered=0;sequence_covered=0;sequence_slots=0
    for position,index in enumerate(chosen):
        file=files[index];parquet=pq.ParquetFile(file)
        count=samples//len(chosen)+(position<samples%len(chosen))
        group=int(rng.integers(parquet.num_row_groups))
        group_rows=parquet.metadata.row_group(group).num_rows
        count=min(count,group_rows);offset=int(rng.integers(group_rows-count+1));seen=0
        # Decode 64 rows at a time, rather than materializing an entire 10K-row
        # group containing two 1K-long sequences per impression.
        for batch in parquet.iter_batches(batch_size=64,row_groups=[group],use_threads=False):
            batch_start=seen;seen+=len(batch)
            start_row=max(offset-batch_start,0);end_row=min(offset+count-batch_start,len(batch))
            if end_row<=start_row:continue
            rows=batch.slice(start_row,end_row-start_row).to_pylist()
            contexts=OrderedDict()
            for row in rows:
                if row['label_0'] not in ([1,0],[0,1]):raise ValueError('Expected [no-click, click] one-hot labels')
                key=tuple(row[k] for k in USER_FIELDS)+(tuple(row['150_2_180']),tuple(row['151_2_180']))
                contexts.setdefault(key,[]).append(row)
            for impressions in contexts.values():
                source=impressions[0];hist=source['150_2_180'];categories=source['151_2_180']
                start=time.perf_counter()
                predicted=model.predict_context(source,hist,categories,impressions)
                inference_seconds+=time.perf_counter()-start
                scores.extend(predicted);labels.extend(row['label_0'][1] for row in impressions)
                users.extend(row['129_1'] for row in impressions)
                target_covered+=int((model.indices(model.scl_keys,[r['205'] for r in impressions])>0).sum())
                valid=[raw for raw in hist if raw]
                sequence_covered+=int((model.indices(model.scl_keys,valid)>0).sum())*len(impressions)
                sequence_slots+=len(valid)*len(impressions)
            if resident_mb()>1000:release_evaluation_pages(model)
            if seen>=offset+count:break
        release_evaluation_pages(model)
        sampling.append({'file':file.name,'row_group':group,'offset':offset,'rows':count})
        print(f'{position+1}/{len(chosen)} shards; {len(labels)} impressions; {time.perf_counter()-started:.1f}s; RSS {resident_mb():.0f} MiB',flush=True)
    metrics=click_metrics(labels,scores,users)
    metrics.update({'target_scl_coverage':target_covered/len(labels),
                    'history_scl_coverage':sequence_covered/sequence_slots if sequence_slots else 0.})
    checkpoints={}
    for name in ('muse_full_training_dense.ckpt','muse_full_training_sparse.ckpt'):
        with (config.CHECKPOINT_DIR/name).open('rb') as stream:
            checkpoints[name]=hashlib.file_digest(stream,'sha256').hexdigest()
    if artifact_signature()!=artifacts or serving_signature()!=code_hash:
        raise RuntimeError('Artifacts or serving code changed during evaluation; rerun')
    evidence=json.dumps({'labels':labels,'scores':scores,'users':users},separators=(',',':')).encode()
    report={'schema_version':2,'run_status':'completed','evaluated_at':datetime.now(timezone.utc).isoformat(),
            'scope':'sampled_taobao_test','sampling':{'seed':seed,'requested_samples':samples,
            'method':'Random shards without replacement; one random contiguous window in a random row group per shard. Original labels and histories; no class balancing.',
            'total_test_rows':sum(pq.ParquetFile(f).metadata.num_rows for f in files),
            'shards':sampling},'artifacts':artifacts,'checkpoint_sha256':checkpoints,
            'predictions_sha256':hashlib.sha256(evidence).hexdigest(),
            'serving_sha256':code_hash,'metrics':metrics,
            'timing':{'inference_seconds':inference_seconds,'wall_seconds':time.perf_counter()-started,
                      'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024},
            'limitations':[
                'Sampled offline impressions, not the full test set or production traffic.',
                'Sample windows cluster by user; do not infer independent-trial confidence intervals.',
                'AUC is pairwise ranking with half credit for ties, not product recommendation accuracy or click probability.',
                'GAUC weights only users with both click and no-click observations by their impression counts.',
                'Precision@10 uses only users with >=20 sampled candidates and both labels; candidate sets are observed test impressions.',
                'Constant CTR baseline uses this sample prevalence; accuracy at 0.5 is compared with always-no-click.',
                'Vietnamese demo names/photos/categories do not match the original Taobao metadata. No labeled Vietnamese shopping evaluation is available.',
                'Serving retrieval, category intent boosts, diversity and commerce rules are outside this checkpoint evaluation.']}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp');temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');temporary.replace(output)
    print(json.dumps(metrics,indent=2));print(f'Report: {output}')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples',type=int,default=2048);parser.add_argument('--shards',type=int,default=4)
    parser.add_argument('--seed',type=int,default=20261015);parser.add_argument('--output',type=Path,default=REPORT_PATH)
    args=parser.parse_args();evaluate(args.samples,args.shards,args.seed,args.output)
