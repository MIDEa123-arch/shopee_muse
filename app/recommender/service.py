import logging
import time
from app.database import connection,public_product


class RecommendationService:
    def __init__(self):
        self.model=None
        self.error=None
        self.last_metrics={}

    def load(self):
        try:
            from .model import MuseModel
            self.model=MuseModel()
            # Warm kernels with actual features; this is not a reported latency measurement.
            sample=list(self.model.items)[:8]
            self.model.predict(next(iter(self.model.users)),sample)
        except Exception as exc:
            self.error=f'{type(exc).__name__}: {exc}'
            logging.exception('MUSE unavailable; catalog fallback is explicitly labeled')

    def status(self):
        return {'ready':self.model is not None,'engine':'Alibaba MUSE / PyTorch CPU' if self.model else 'Catalog fallback',
                'checkpoint_loaded':self.model is not None,'scl_dimensions':128 if self.model else None,
                'gsu_top_k':50 if self.model else None,'history_limit':1000,
                'source':'https://github.com/alimama-tech/MUSE','last_metrics':self.last_metrics}

    def recommend(self,user_id=None,touchpoint='home',product_id=None,limit=24):
        start=time.perf_counter()
        with connection() as db:
            products=[dict(r) for r in db.execute('''SELECT p.*,pr.name province_name FROM products p
                LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.stock>0 ORDER BY p.id''')]
            cart_ids={r['product_id'] for r in db.execute('SELECT product_id FROM cart_items WHERE user_id=?',(user_id,))} if user_id else set()
            subtotal=db.execute('SELECT COALESCE(SUM(p.price*c.quantity),0) FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.user_id=? AND c.is_selected=1',(user_id,)).fetchone()[0] if user_id else 0
        model=self.model;metadata={};strategy='popular';engine='Catalog fallback';metric='popularity'
        if model:
            products=[p for p in products if p['raw_item_id'] in model.items]
        if touchpoint=='cart':
            remaining=max(0,150000-subtotal)
            # Prefer the requested 30–60k band, but never invent cheap catalog items.
            products=[p for p in products if p['id'] not in cart_ids]
            low=[p for p in products if 30000<=p['price']<=max(60000,remaining)]
            if low:
                products=low
            else:
                products=sorted(products,key=lambda p:p['price'])[:80]
            metadata['free_shipping_remaining']=remaining
        products=[p for p in products if p['id']!=product_id]
        inference_start=time.perf_counter()
        if model and products:
            ids=[p['raw_item_id'] for p in products]
            if touchpoint=='similar' and product_id:
                with connection() as db:
                    target=db.execute('SELECT raw_item_id FROM products WHERE id=?',(product_id,)).fetchone()
                if target and target['raw_item_id'] in model.items:
                    scores=model.similarities(target['raw_item_id'],ids)
                    metric='cosine_similarity';strategy='SCL cosine / GSU';engine='MUSE SCL 128D'
                    for p,s in zip(products,scores):
                        p['similarity']=round(s,6)
                else:
                    scores=[p['sold_count'] for p in products]
            elif user_id:
                scores,extra=model.predict(user_id,ids)
                metadata.update(extra);metric='p_click';strategy='GSU → SimTier + SA-TA → ESU';engine='Alibaba MUSE'
                for p,s in zip(products,scores):
                    p['p_click']=round(s,7)
            else:
                scores=[p['sold_count'] for p in products];engine='Popular / guest'
        else:
            scores=[p['sold_count'] for p in products]
        inference_ms=(time.perf_counter()-inference_start)*1000
        ranked=sorted(zip(products,scores),key=lambda x:(x[1],x[0]['sold_count']),reverse=True)
        top=[public_product(p) for p,s in ranked[:limit]]
        metadata.update({'engine':engine,'strategy':strategy,'score_type':metric,'candidate_count':len(products),
                         'inference_ms':round(inference_ms,2),'latency_ms':round((time.perf_counter()-start)*1000,2),
                         'checkpoint_loaded':model is not None,'touchpoint':touchpoint})
        self.last_metrics=metadata
        if user_id:
            with connection(write=True) as db:
                db.execute('''INSERT INTO recommendation_logs(user_id,touchpoint,candidate_count,top_recommended_ids,model_name,latency_ms)
                    VALUES (?,?,?,?,?,?)''',(user_id,touchpoint,len(products),','.join(str(x['id']) for x in top),engine,metadata['latency_ms']))
        return {'items':top,'meta':metadata}


service=RecommendationService()
