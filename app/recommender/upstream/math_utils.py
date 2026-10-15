"""Small CPU-safe helpers retained from upstream utils/utils.py (Apache-2.0)."""
import torch


def clip_prop(prop):
    return torch.clamp(prop,0.0,1.0)


def get_cosine(item,seq,steps,n_dim,indicator=None,sorted=False,int8=True):
    item=torch.nn.functional.normalize(item.float().reshape(-1,1,n_dim),dim=2)
    seq=torch.nn.functional.normalize(seq.float().reshape(-1,steps,n_dim),dim=2)
    if indicator is not None:
        seq=torch.index_select(seq,index=indicator,dim=0)
    cosine=(item*seq).sum(dim=2)
    return torch.sort(cosine,dim=-1,descending=True) if sorted else cosine


def write_info_to_file(*args,**kwargs):
    pass
