from fastapi import APIRouter,Depends,HTTPException,Query
from app.database import connection
from app.security import current_user,require_demo,require_user
from app.services.behavior import record_behavior
from app.recommender.service import service
from app.recommender.evaluation import evaluation_summary,REPORT_PATH
from app.native_catalog import MODE,catalog_info
from app.recommender.experience import experience_summary
from app.recommender.native import native_ranking
from app.recommender.commerce import complementary_bundle, personalized_deals
import json

router=APIRouter(prefix='/api/recommendations',tags=['recommendations'])


@router.get('/bundle')
def recommendation_bundle(focus_product_id: int | None = Query(None, ge=1), user = Depends(current_user)):
    with connection() as db:
        return complementary_bundle(db, user['id'] if user else None, focus_product_id)


@router.get('/deals')
def recommendation_deals(limit: int = Query(12, ge=1, le=30), user = Depends(current_user)):
    with connection() as db:
        return personalized_deals(db, user['id'] if user else None, limit)


def active_demo_interest(db,user_id):
    row=db.execute('''SELECT p.category_id,c.name category_name,p.id product_id,h.created_at
        FROM user_behavior_history h JOIN products p ON p.id=h.product_id
        JOIN categories c ON c.id=p.category_id
        WHERE h.user_id=? AND h.action_type='demo_interest'
        ORDER BY h.id DESC LIMIT 1''',(user_id,)).fetchone()
    return dict(row) if row else None


@router.get('')
def recommendations(touchpoint:str=Query('home',pattern='^(home|similar|cart|complementary|orders|post_purchase|deals)$'),product_id:int|None=None,
                    limit:int=Query(24,ge=1,le=60),category_id:int|None=None,
                    display_category:str=Query('',max_length=40),
                    presentation_policy:str=Query('original',pattern='^(original|contextual|browse|feed)$'),
                    focus_product_id:int|None=Query(None,ge=1),order_id:int|None=Query(None,ge=1),user=Depends(current_user)):
    if touchpoint in ('similar','complementary') and product_id is None:
        raise HTTPException(422,'Cần chọn sản phẩm để tìm gợi ý liên quan.')
    return service.recommend(user['id'] if user else None,touchpoint,product_id,limit,category_id,display_category,presentation_policy,focus_product_id,order_id=order_id)


@router.post('/behavior/{product_id}')
def behavior(product_id:int,user=Depends(require_user)):
    with connection(write=True) as db:
        product=db.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone()
        if not product:
            raise HTTPException(404,'Sản phẩm không tồn tại.')
        record_behavior(db,user,product,'click')
        # At most one personalized deal notification per user per day.
        if product['discount_percent']>=30 and not db.execute("SELECT 1 FROM notifications WHERE user_id=? AND type='personalized' AND date(created_at)=date('now')",(user['id'],)).fetchone():
            db.execute("INSERT INTO notifications(user_id,title,content,type) VALUES (?,?,?,'personalized')",
                (user['id'],'Ưu đãi từ món bạn vừa quan tâm',f"{product['name']} đang giảm {product['discount_percent']}%. Khám phá thêm sản phẩm tương tự!"))
    return {'ok':True}


@router.get('/experience')
def experience(user=Depends(current_user)):
    with connection() as db:
        if catalog_info(db)['mode']!=MODE:
            raise HTTPException(404,'Trải nghiệm này dùng danh mục Taobao gốc.')
    return experience_summary(user['id'] if user else None)


@router.get('/compare-profiles',dependencies=[Depends(require_demo)])
def compare_profiles(left:int=1,right:int=2,presentation_policy:str=Query('original',pattern='^(original|browse)$')):
    with connection() as db:
        if catalog_info(db)['mode']!=MODE:
            raise HTTPException(404,'So sánh này dùng danh mục Taobao gốc.')
        profiles={r['id']:dict(r) for r in db.execute('''SELECT u.id,u.full_name FROM users u
            JOIN muse_user_features f ON f.user_id=u.id''')}
    if left not in profiles or right not in profiles:
        raise HTTPException(404,'Chỉ so sánh các hồ sơ Taobao mẫu.')
    if left==right:
        raise HTTPException(422,'Chọn hai hồ sơ khác nhau để so sánh.')
    results=[]
    for uid in (left,right):
        result=native_ranking.recommend(service,uid,'home',None,12,write_logs=False,presentation_policy=presentation_policy)
        results.append({'profile':profiles[uid],'items':result['items'],'model_used':result['meta']['model_used'],
                        'history_length':result['meta'].get('history_length',0)})
    key=lambda p:p.get('template_id',p['id']) if presentation_policy=='browse' else p['id']
    overlap=len({key(p) for p in results[0]['items']}&{key(p) for p in results[1]['items']})
    return {'left':results[0],'right':results[1],'shared_items':overlap,
            'scope':'same_catalog_distinct_histories_with_seen_items_filtered',
            'read_only':True}


@router.get('/demo-state',dependencies=[Depends(require_demo)])
def demo_state(user=Depends(require_user)):
    with connection() as db:
        return {'active_interest':active_demo_interest(db,user['id'])}


@router.post('/demo-interest/{category_id}',dependencies=[Depends(require_demo)])
def demo_interest(category_id:int,user=Depends(require_user)):
    with connection(write=True) as db:
        if catalog_info(db)['mode']==MODE:
            raise HTTPException(409,'Chọn nhóm bằng bộ lọc khám phá; không ghi lượt xem giả vào lịch sử AI.')
        category=db.execute('SELECT id,name FROM categories WHERE id=?',(category_id,)).fetchone()
        product=db.execute('''SELECT * FROM products WHERE category_id=? AND stock>0
            ORDER BY rating_star DESC,sold_count DESC,id LIMIT 1''',(category_id,)).fetchone()
        if not category or not product:
            raise HTTPException(404,'Nhóm sở thích không khả dụng.')
        # Only the presentation signal is replaced. Imported history and real web actions stay intact.
        db.execute("DELETE FROM user_behavior_history WHERE user_id=? AND action_type='demo_interest'",(user['id'],))
        record_behavior(db,user,product,'demo_interest')
        return {'active_interest':active_demo_interest(db,user['id'])}


@router.delete('/demo-interest',dependencies=[Depends(require_demo)])
def clear_demo_interest(user=Depends(require_user)):
    with connection(write=True) as db:
        db.execute("DELETE FROM user_behavior_history WHERE user_id=? AND action_type='demo_interest'",(user['id'],))
    return {'active_interest':None}


@router.get('/debug',dependencies=[Depends(require_demo)])
def debug(user=Depends(require_user)):
    with connection() as db:
        total=db.execute('SELECT COUNT(*) FROM user_behavior_history WHERE user_id=?',(user['id'],)).fetchone()[0]
        logs=[dict(r) for r in db.execute('SELECT * FROM recommendation_logs WHERE user_id=? ORDER BY id DESC LIMIT 10',(user['id'],))]
    state=service.status(user['id'])
    quality=evaluation_summary()
    state.update({'user_id':user['id'],'raw_user_id':str(user['raw_user_id']) if user['raw_user_id'] is not None else None,
                  'history_count':total,'error':service.error,'recent_runs':logs,
                  'training_metrics':{'gauc':0.614794,'auc':0.644728,'test_loss':0.383716,
                      'source':'User-provided experiment report; not re-evaluated by this web app'},
                  'evaluation':json.loads(REPORT_PATH.read_text()) if quality['available'] else quality,
                  'catalog_note':'Original Taobao IDs, groups and histories. Independent illustrative commerce presentation may be attached; it is not original Taobao merchandise metadata. Simulated commerce.' if catalog_native()
                  else 'Vietnamese names, categories, prices and stock photos are demo merchandising mapped to Taobao raw IDs; they do not describe original Taobao items.'})
    return state

def catalog_native():
    with connection() as db:
        return catalog_info(db)['mode']==MODE


@router.get('/history',dependencies=[Depends(require_demo)])
def history(limit:int=Query(1000,ge=1,le=1000),user=Depends(require_user)):
    with connection() as db:
        return [{**dict(r),'raw_item_id':str(r['raw_item_id']),'raw_user_id':str(r['raw_user_id'])} for r in db.execute('''SELECT h.*,
            COALESCE(pp.name, p.name) product_name,
            COALESCE(pp.image_url, p.image_url) image_url,
            COALESCE(pp.category_name, c.name) category_name
            FROM user_behavior_history h
            LEFT JOIN products p ON p.id=h.product_id
            LEFT JOIN product_presentations pp ON pp.product_id=h.product_id
            LEFT JOIN categories c ON c.id=p.category_id
            WHERE h.user_id=? ORDER BY h.id DESC LIMIT ?''',(user['id'],limit))]
