"""CPU serving adapter for the original MUSE forward pass and exact ID maps."""
import json
import ctypes
import mmap
import os
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


def mapped_array(path):
    array=np.load(path,mmap_mode='r')
    # ID lookups touch scattered pages in multi-GB tables. Sequential readahead
    # needlessly loads gigabytes and evicts the web process on smaller machines.
    if hasattr(array._mmap,'madvise') and hasattr(mmap,'MADV_RANDOM'):
        array._mmap.madvise(mmap.MADV_RANDOM)
    return array


def advise_random_weights(weights):
    """Disable sequential readahead for scattered lookups in Torch's mapped file.

    This changes only the kernel's paging hint, never checkpoint values. Tensor
    storage owns the mapping; keep it alive while passing its aligned range.
    """
    if os.name!='posix' or not hasattr(mmap,'MADV_RANDOM'):
        return
    libc=ctypes.CDLL(None)
    if not hasattr(libc,'madvise'):
        return
    advise=libc.madvise
    advise.argtypes=(ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int)
    advise.restype=ctypes.c_int
    page=os.sysconf('SC_PAGE_SIZE')
    for tensor in weights.values():
        storage=tensor.untyped_storage();address=storage.data_ptr();size=storage.nbytes()
        base=address-address%page
        if size:
            advise(base,address+size-base,mmap.MADV_RANDOM)


class ItemFeatureStore(dict):
    def __init__(self, initial=None):
        super().__init__(initial or {})
        self._cache = {}

    def register_products(self, products):
        for p in products:
            if not isinstance(p, dict):
                p = dict(p)
            raw = p.get('raw_item_id')
            if raw is None:
                continue
            k = int(raw)
            if super().__contains__(k) or k in self._cache:
                continue
            sc = p.get('source_category_id')
            if sc:
                self._cache[k] = {
                    '205': k,
                    '206': int(sc),
                    '213': int(p.get('source_city_id') or 0),
                    '214': int(p.get('source_province_id') or 0),
                }

    def __contains__(self, key):
        k = int(key) if key is not None else None
        if super().__contains__(k) or k in self._cache:
            return True
        try:
            with connection() as db:
                row = db.execute("SELECT raw_item_id, source_category_id, source_city_id, source_province_id FROM products WHERE raw_item_id=?", (k,)).fetchone()
                if row and row['source_category_id']:
                    self._cache[k] = {
                        '205': int(row['raw_item_id']),
                        '206': int(row['source_category_id']),
                        '213': int(row['source_city_id']),
                        '214': int(row['source_province_id']),
                    }
                    return True
        except Exception:
            pass
        return False

    def __getitem__(self, key):
        k = int(key) if key is not None else 0
        if super().__contains__(k):
            return super().__getitem__(k)
        if k in self._cache:
            return self._cache[k]
        if k in self:
            return self._cache[k]
        return {'205': k, '206': 0, '213': 0, '214': 0}

    def get(self, key, default=None):
        if key in self:
            return self[key]
        return default


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
        advise_random_weights(self.sparse)
        self.maps={}
        feature_dir=config.DATASET_DIR/'feature_map'
        for field in SPARSE_FIELDS:
            suffix='_p90' if field=='150_2_180' else ''
            self.maps[field]=mapped_array(feature_dir/f'{field}_sorted_map{suffix}.npy')
            if len(self.maps[field])+1!=self.sparse[field+'.weight'].shape[0]:
                raise ValueError(f'Checkpoint vocabulary mismatch: {field}')
        self.scl_keys=mapped_array(feature_dir/'scl_emb_int8_p90_keys.npy')
        self.scl_values=mapped_array(feature_dir/'scl_emb_int8_p90_values.npy')
        if self.scl_values.shape!=(len(self.scl_keys),128):
            raise ValueError('SCL key/value dimensions do not match the checkpoint')
        with connection() as db:
            initial_items={r['raw_item_id']:json.loads(r['features_json']) for r in db.execute('SELECT * FROM muse_item_features')}
            self.items=ItemFeatureStore(initial_items)
            self.users={r['user_id']:json.loads(r['features_json']) for r in db.execute('SELECT * FROM muse_user_features')}
        if not self.items or not self.users:
            raise ValueError('Run python scripts/prepare_muse.py to import authentic model features')
        raw_ids=sorted(set(initial_items)|{raw for row in self.users.values() for raw in row['150_2_180'] if raw})
        # Cache only the initial subset, keeping multi-GB source tables memory-mapped.
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
        uncached=sorted({int(x) for x in raw if int(x) not in self.vector_cache and x!=0})
        if uncached:
            scl_vecs=self.scl(uncached)
            for i,x in enumerate(uncached):
                self.vector_cache[x]=scl_vecs[i]
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
            live=list(db.execute("""SELECT h.raw_item_id, p.source_category_id, p.source_city_id, p.source_province_id
                FROM user_behavior_history h LEFT JOIN products p ON p.id=h.product_id
                WHERE h.user_id=? AND h.action_type!='imported_click' ORDER BY h.id DESC LIMIT 1000""",(user_id,)))
        self.items.register_products(live)
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
        scores=self.predict_context(source,hist,categories,[self.items[x] for x in raw_ids],cached=True)
        coverage=sum(bool(torch.count_nonzero(self.vector_cache.get(raw,torch.zeros(128)))) for raw in raw_ids)/len(raw_ids)
        return scores,{'history_length':actual,'scl_coverage':round(coverage,4),'cold_start':user_id not in self.users}

    @torch.inference_mode()
    def predict_context(self,source,hist,categories,item_features,*,cached=False):
        """Shared serving/evaluation path; evaluation never reads or changes web history.

        Each evaluation context comes directly from a labeled held-out impression.
        Target features need not exist in the demo catalog. No label enters inference.
        """
        if not item_features:
            return []
        if len(hist)!=len(categories):
            raise ValueError('History item/category sequences must be paired')
        hist=([0]*1000+list(hist))[-1000:]
        categories=([0]*1000+list(categories))[-1000:]
        vectors=self.vectors if cached else self.scl
        hist_vectors=vectors(hist)
        short_vectors=hist_vectors[-50:]
        hist_embeddings=torch.cat([self.embedding('150_2_180',hist),self.embedding('151_2_180',categories)],dim=-1)
        scores=[]
        with self.lock:
            for start in range(0,len(item_features),64):
                features=item_features[start:start+64]
                ids=[x['205'] for x in features];n=len(ids)
                target=vectors(ids)
                similarity=F.normalize(target,dim=-1) @ F.normalize(hist_vectors,dim=-1).T
                # Match upstream GSU masking, top-k order and padding.
                similarity=similarity.masked_fill(similarity==0,-1.1)
                indices=torch.topk(similarity,k=50,dim=1,sorted=True).indices
                selected=hist_embeddings[indices]
                users=[self.embedding(k,[source.get(k,0)]).expand(n,-1) for k in USER_FIELDS]
                ads=[self.embedding('150_2_180',ids),
                     self.embedding('151_2_180',[x['206'] for x in features]),
                     self.embedding('213',[x['213'] for x in features]),
                     self.embedding('214',[x['214'] for x in features]),target]
                _,prop=self.network(users,ads,
                    [selected[:,:,:16],selected[:,:,16:],hist_vectors[indices]],
                    [hist_embeddings[-50:,:16].unsqueeze(0).expand(n,-1,-1),hist_embeddings[-50:,16:].unsqueeze(0).expand(n,-1,-1),short_vectors.unsqueeze(0).expand(n,-1,-1)],
                    torch.zeros(n,2))
                if not torch.isfinite(prop).all():
                    raise RuntimeError('Non-finite checkpoint output')
                scores.extend(prop[:,1].tolist())
        return scores

    @torch.inference_mode()
    def retrieve_gsu(self,user_id,raw_ids,top_k=128):
        if not raw_ids or len(raw_ids)<=top_k:
            return raw_ids
        source,hist,categories,actual=self.history(user_id)
        valid_hist=[x for x in hist if x]
        if not valid_hist:
            return raw_ids[:top_k]
        targets=self.vectors(raw_ids)
        hist_vecs=self.vectors(valid_hist[-50:])
        sims=(F.normalize(targets,dim=-1) @ F.normalize(hist_vecs,dim=-1).T).max(dim=1).values
        k=min(top_k,len(raw_ids))
        top_indices=torch.topk(sims,k=k).indices.tolist()
        return [raw_ids[i] for i in top_indices]

    @torch.inference_mode()
    def similarities(self,raw_id,raw_ids):
        target=F.normalize(self.vectors([raw_id]),dim=-1)
        return (F.normalize(self.vectors(raw_ids),dim=-1) @ target.T).flatten().tolist()
