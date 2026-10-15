"""CPU serving adapter for the original MUSE forward pass and exact ID maps."""
import json
import threading
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from app import config
from app.database import connection
from .upstream.muse import MUSE_DIN

USER_FIELDS=['129_1','130_1','130_2','130_3','130_4','130_5']
SPARSE_FIELDS=USER_FIELDS+['150_2_180','151_2_180','213','214']


class MuseModel:
    def __init__(self):
        self.lock=threading.Lock()
        torch.set_num_threads(2)
        checkpoint=config.CHECKPOINT_DIR
        dense=torch.load(checkpoint/'muse_full_training_dense.ckpt',map_location='cpu',weights_only=True)
        self.network=MUSE_DIN(args={'method':'muse','use_aux_loss':False},D=16,RT_STEPS=50,UNI_STEPS=50)
        for name,state in dense.items():
            getattr(self.network,name).load_state_dict(state,strict=True)
        self.network.eval()
        self.sparse=torch.load(checkpoint/'muse_full_training_sparse.ckpt',map_location='cpu',weights_only=True,mmap=True)['embedding_layers']
        self.maps={}
        feature_dir=config.DATASET_DIR/'feature_map'
        for field in SPARSE_FIELDS:
            suffix='_p90' if field=='150_2_180' else ''
            self.maps[field]=np.load(feature_dir/f'{field}_sorted_map{suffix}.npy',mmap_mode='r')
            if len(self.maps[field])+1!=self.sparse[field+'.weight'].shape[0]:
                raise ValueError(f'Checkpoint vocabulary mismatch: {field}')
        self.scl_keys=np.load(feature_dir/'scl_emb_int8_p90_keys.npy',mmap_mode='r')
        self.scl_values=np.load(feature_dir/'scl_emb_int8_p90_values.npy',mmap_mode='r')
        with connection() as db:
            self.items={r['raw_item_id']:json.loads(r['features_json']) for r in db.execute('SELECT * FROM muse_item_features')}
            self.users={r['user_id']:json.loads(r['features_json']) for r in db.execute('SELECT * FROM muse_user_features')}
        if not self.items or not self.users:
            raise ValueError('Run python scripts/prepare_muse.py to import authentic model features')
        raw_ids=sorted(set(self.items)|{raw for row in self.users.values() for raw in row['150_2_180'] if raw})
        # Cache only the demo subset, keeping multi-GB source tables memory-mapped.
        vectors=self.scl(raw_ids)
        self.vector_cache={raw:vectors[i] for i,raw in enumerate(raw_ids)}

    @staticmethod
    def indices(keys,raw):
        raw=np.asarray(raw,dtype=np.int64)
        positions=np.searchsorted(keys,raw)
        safe=np.minimum(positions,len(keys)-1)
        valid=(positions<len(keys)) & (keys[safe]==raw)
        return np.where(valid,positions+1,0)

    def embedding(self,field,raw):
        mapped=self.indices(self.maps[field],raw)
        return self.sparse[field+'.weight'][torch.as_tensor(mapped,dtype=torch.long)]

    def scl(self,raw):
        indices=self.indices(self.scl_keys,raw)
        values=np.zeros((*indices.shape,128),dtype=np.float32)
        mask=indices>0
        values[mask]=self.scl_values[indices[mask]-1].astype(np.float32)
        return torch.from_numpy(values)

    def vectors(self,raw):
        zero=torch.zeros(128)
        return torch.stack([self.vector_cache.get(int(x),zero) for x in raw])

    def history(self,user_id):
        source=self.users.get(user_id)
        if not source:
            source={k:0 for k in USER_FIELDS}
            items=[];categories=[]
        else:
            items=list(source['150_2_180']);categories=list(source['151_2_180'])
        with connection() as db:
            # Imported interactions already appear in the original paired sequence.
            live=list(db.execute("SELECT raw_item_id FROM user_behavior_history WHERE user_id=? AND action_type!='imported_click' ORDER BY id DESC LIMIT 1000",(user_id,)))
        for r in reversed(live):
            raw=r['raw_item_id'];feature=self.items.get(raw)
            items.append(raw);categories.append(feature['206'] if feature else 0)
        actual=min(len([x for x in items if x]),1000)
        items=([0]*1000+items)[-1000:];categories=([0]*1000+categories)[-1000:]
        return source,items,categories,actual

    @torch.inference_mode()
    def predict(self,user_id,raw_ids):
        if not raw_ids:
            return [],{'history_length':0,'scl_coverage':0}
        source,hist,categories,actual=self.history(user_id)
        hist_vectors=self.vectors(hist)
        short_vectors=hist_vectors[-50:]
        hist_embeddings=torch.cat([self.embedding('150_2_180',hist),self.embedding('151_2_180',categories)],dim=-1)
        scores=[]
        with self.lock:
            for start in range(0,len(raw_ids),64):
                ids=raw_ids[start:start+64];n=len(ids)
                target=self.vectors(ids)
                similarity=F.normalize(target,dim=-1) @ F.normalize(hist_vectors,dim=-1).T
                # Match upstream GSU masking, top-k order and padding.
                similarity=similarity.masked_fill(similarity==0,-1.1)
                indices=torch.topk(similarity,k=50,dim=1,sorted=True).indices
                selected=hist_embeddings[indices]
                users=[self.embedding(k,[source.get(k,0)]).expand(n,-1) for k in USER_FIELDS]
                item_features=[self.items[x] for x in ids]
                ads=[self.embedding('150_2_180',ids),
                     self.embedding('151_2_180',[x['206'] for x in item_features]),
                     self.embedding('213',[x['213'] for x in item_features]),
                     self.embedding('214',[x['214'] for x in item_features]),target]
                _,prop=self.network(users,ads,
                    [selected[:,:,:16],selected[:,:,16:],hist_vectors[indices]],
                    [hist_embeddings[-50:,:16].unsqueeze(0).expand(n,-1,-1),hist_embeddings[-50:,16:].unsqueeze(0).expand(n,-1,-1),short_vectors.unsqueeze(0).expand(n,-1,-1)],
                    torch.zeros(n,2))
                if not torch.isfinite(prop).all():
                    raise RuntimeError('Non-finite checkpoint output')
                scores.extend(prop[:,1].tolist())
        coverage=sum(bool(torch.count_nonzero(self.vector_cache.get(raw,torch.zeros(128)))) for raw in raw_ids)/len(raw_ids)
        return scores,{'history_length':actual,'scl_coverage':round(coverage,4),'cold_start':user_id not in self.users}

    @torch.inference_mode()
    def similarities(self,raw_id,raw_ids):
        target=F.normalize(self.vectors([raw_id]),dim=-1)
        return (F.normalize(self.vectors(raw_ids),dim=-1) @ target.T).flatten().tolist()
