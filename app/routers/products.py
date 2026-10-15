import unicodedata
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from app.database import connection, public_product
from app.security import require_user

router=APIRouter(prefix='/api',tags=['catalog'])
PRODUCT_SQL='''SELECT p.*,c.name category_name,pr.name province_name FROM products p
    LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN provinces pr ON pr.id=p.province_id'''


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower().replace('đ','d')) if unicodedata.category(c)!='Mn')


@router.get('/catalog')
def catalog():
    with connection() as db:
        return {'categories':[dict(r) for r in db.execute('SELECT c.*,COUNT(p.id) product_count FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id')],
                'provinces':[dict(r) for r in db.execute('SELECT * FROM provinces ORDER BY id')],
                'product_count':db.execute('SELECT COUNT(*) FROM products').fetchone()[0]}


@router.get('/products')
def products(q:str=Query('',max_length=100),category_id:int|None=None,province_id:int|None=None,
             min_price:int=Query(0,ge=0),max_price:int|None=Query(None,ge=0),
             sort:str=Query('popular',pattern='^(popular|price_asc|price_desc|newest|sold|rating|discount)$'),
             page:int=Query(1,ge=1),page_size:int=Query(24,ge=1,le=60),mall:bool=False):
    clauses=['p.stock>0'];params=[]
    for column,value in [('category_id',category_id),('province_id',province_id)]:
        if value is not None:
            clauses.append(f'p.{column}=?');params.append(value)
    clauses.append('p.price>=?');params.append(min_price)
    if max_price is not None:
        clauses.append('p.price<=?');params.append(max_price)
    if mall:
        clauses.append('p.is_mall=1')
    order={'popular':'p.rating_star DESC,p.sold_count DESC','price_asc':'p.price ASC','price_desc':'p.price DESC',
           'newest':'p.id DESC','sold':'p.sold_count DESC','rating':'p.rating_star DESC,p.rating_count DESC','discount':'p.discount_percent DESC'}[sort]
    with connection() as db:
        db.create_function('normalize',1,normalize)
        for term in normalize(q).split():
            clauses.append("normalize(p.name || ' ' || p.shop_name) LIKE ? ESCAPE '\\'")
            params.append('%'+term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
        where=' WHERE '+' AND '.join(clauses)
        total=db.execute('SELECT COUNT(*) FROM products p'+where,params).fetchone()[0]
        rows=db.execute(PRODUCT_SQL+where+' ORDER BY '+order+',p.id LIMIT ? OFFSET ?',params+[page_size,(page-1)*page_size])
        return {'items':[public_product(r) for r in rows],'total':total,'page':page,'page_size':page_size,'pages':(total+page_size-1)//page_size}


@router.get('/products/{product_id}')
def product(product_id:int):
    with connection() as db:
        row=db.execute(PRODUCT_SQL+' WHERE p.id=?',(product_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Sản phẩm không tồn tại.')
        result=public_product(row)
        result['reviews']=[dict(r) for r in db.execute('SELECT r.rating,r.content,r.created_at,u.full_name FROM reviews r JOIN users u ON u.id=r.user_id WHERE product_id=? ORDER BY r.id DESC LIMIT 20',(product_id,))]
        return result


class Review(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    rating:int=Field(ge=1,le=5)
    content:str=Field(min_length=10,max_length=1000)


@router.post('/products/{product_id}/reviews',status_code=201)
def review(product_id:int,body:Review,user=Depends(require_user)):
    with connection(write=True) as db:
        if not db.execute("SELECT 1 FROM orders o JOIN order_items i ON i.order_id=o.id WHERE o.user_id=? AND i.product_id=? AND o.order_status='Đã giao'",(user['id'],product_id)).fetchone():
            raise HTTPException(403,'Bạn có thể đánh giá sau khi nhận sản phẩm.')
        if db.execute('SELECT 1 FROM reviews WHERE user_id=? AND product_id=?',(user['id'],product_id)).fetchone():
            raise HTTPException(409,'Bạn đã đánh giá sản phẩm này.')
        db.execute('INSERT INTO reviews(user_id,product_id,rating,content) VALUES (?,?,?,?)',(user['id'],product_id,body.rating,body.content.strip()))
    return {'ok':True}
