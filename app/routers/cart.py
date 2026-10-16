from fastapi import APIRouter,Depends,HTTPException
from app.database import connection
from app.schemas import CartAdd,CartUpdate,CartSelection
from app.security import require_user
from app.services.behavior import record_behavior
from app.services.cart import cart_rows
from app.services.shipping import shipping_groups

router=APIRouter(prefix='/api/cart',tags=['cart'])


@router.get('')
def cart(user=Depends(require_user)):
    with connection() as db:
        items=cart_rows(db,user['id'])
        return {'items':items,'count':sum(x['quantity'] for x in items),
                'subtotal':sum(x['price']*x['quantity'] for x in items if x['is_selected']),
                'shipping_groups':shipping_groups([x for x in items if x['is_selected']])}


@router.post('',status_code=201)
def add(body:CartAdd,user=Depends(require_user)):
    with connection(write=True) as db:
        product=db.execute('SELECT * FROM products WHERE id=?',(body.product_id,)).fetchone()
        if not product:
            raise HTTPException(404,'Sản phẩm không tồn tại.')
        current=db.execute('SELECT quantity FROM cart_items WHERE user_id=? AND product_id=?',(user['id'],body.product_id)).fetchone()
        quantity=(current['quantity'] if current else 0)+body.quantity
        if quantity>min(product['stock'],99):
            raise HTTPException(409,'Số lượng vượt quá tồn kho hoặc giới hạn 99 sản phẩm.')
        db.execute('''INSERT INTO cart_items(user_id,product_id,quantity) VALUES (?,?,?)
            ON CONFLICT(user_id,product_id) DO UPDATE SET quantity=excluded.quantity,is_selected=1''',(user['id'],body.product_id,quantity))
        record_behavior(db,user,product,'add_to_cart')
    return {'ok':True}


@router.put('/selection')
def select_all(body:CartSelection,user=Depends(require_user)):
    with connection(write=True) as db:
        # Unavailable rows remain deselected so they cannot block the valid purchase.
        db.execute('''UPDATE cart_items SET is_selected=CASE WHEN ? AND quantity<=
            (SELECT stock FROM products WHERE id=cart_items.product_id) THEN 1 ELSE 0 END
            WHERE user_id=?''',(body.is_selected,user['id']))
    return {'ok':True}


@router.put('/{item_id}')
def update(item_id:int,body:CartUpdate,user=Depends(require_user)):
    with connection(write=True) as db:
        item=db.execute('SELECT c.*,p.stock FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.id=? AND c.user_id=?',(item_id,user['id'])).fetchone()
        if not item:
            raise HTTPException(404,'Không tìm thấy sản phẩm trong giỏ.')
        if body.quantity>item['stock'] and (body.is_selected or body.quantity!=item['quantity']):
            raise HTTPException(409,'Số lượng vượt quá tồn kho.')
        db.execute('UPDATE cart_items SET quantity=?,is_selected=? WHERE id=?',(body.quantity,int(body.is_selected),item_id))
    return {'ok':True}


@router.delete('/{item_id}')
def remove(item_id:int,user=Depends(require_user)):
    with connection(write=True) as db:
        if not db.execute('DELETE FROM cart_items WHERE id=? AND user_id=?',(item_id,user['id'])).rowcount:
            raise HTTPException(404,'Không tìm thấy sản phẩm trong giỏ.')
    return {'ok':True}
