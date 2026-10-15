from fastapi import APIRouter,Depends,HTTPException,Query
from app.database import connection
from app.security import current_user,require_demo,require_user
from app.services.behavior import record_behavior
from app.recommender.service import service

router=APIRouter(prefix='/api/recommendations',tags=['recommendations'])


@router.get('')
def recommendations(touchpoint:str=Query('home',pattern='^(home|similar|cart)$'),product_id:int|None=None,
                    limit:int=Query(24,ge=1,le=60),user=Depends(current_user)):
    if touchpoint=='similar' and product_id is None:
        raise HTTPException(422,'Cần chọn sản phẩm để tìm sản phẩm tương tự.')
    return service.recommend(user['id'] if user else None,touchpoint,product_id,limit)


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


@router.get('/debug',dependencies=[Depends(require_demo)])
def debug(user=Depends(require_user)):
    with connection() as db:
        total=db.execute('SELECT COUNT(*) FROM user_behavior_history WHERE user_id=?',(user['id'],)).fetchone()[0]
        logs=[dict(r) for r in db.execute('SELECT * FROM recommendation_logs WHERE user_id=? ORDER BY id DESC LIMIT 10',(user['id'],))]
    state=service.status()
    state.update({'user_id':user['id'],'raw_user_id':str(user['raw_user_id']) if user['raw_user_id'] is not None else None,
                  'history_count':total,'error':service.error,'recent_runs':logs,
                  'training_metrics':{'gauc':0.614794,'auc':0.644728,'test_loss':0.383716,
                      'source':'User-provided experiment report; not re-evaluated by this web app'},
                  'catalog_note':'Vietnamese names, categories, prices and stock photos are demo merchandising mapped to Taobao raw IDs; they do not describe original Taobao items.'})
    return state


@router.get('/history',dependencies=[Depends(require_demo)])
def history(limit:int=Query(1000,ge=1,le=1000),user=Depends(require_user)):
    with connection() as db:
        return [{**dict(r),'raw_item_id':str(r['raw_item_id']),'raw_user_id':str(r['raw_user_id'])} for r in db.execute('''SELECT h.*,p.name product_name FROM user_behavior_history h
            LEFT JOIN products p ON p.id=h.product_id WHERE h.user_id=? ORDER BY h.id DESC LIMIT ?''',(user['id'],limit))]
