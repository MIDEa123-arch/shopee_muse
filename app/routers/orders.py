import hashlib
import json
import secrets
from fastapi import APIRouter,Depends,HTTPException
from app import config
from app.database import connection
from app.schemas import Checkout,OrderCreate
from app.security import require_demo,require_user
from app.services.behavior import record_behavior
from app.services.checkout import calculate,today

router=APIRouter(prefix='/api',tags=['orders'])


@router.get('/vouchers')
def vouchers(user=Depends(require_user)):
    with connection() as db:
        return [dict(r) for r in db.execute('''SELECT v.*,COALESCE(uv.status,'unclaimed') status FROM vouchers v
            LEFT JOIN user_vouchers uv ON uv.voucher_id=v.id AND uv.user_id=? WHERE v.end_date>=? ORDER BY v.id''',(user['id'],today()))]


@router.post('/vouchers/{voucher_id}/claim')
def claim(voucher_id:int,user=Depends(require_user)):
    with connection(write=True) as db:
        if not db.execute('SELECT 1 FROM vouchers WHERE id=? AND end_date>=?',(voucher_id,today())).fetchone():
            raise HTTPException(404,'Voucher không khả dụng.')
        db.execute("INSERT OR IGNORE INTO user_vouchers(user_id,voucher_id) VALUES (?,?)",(user['id'],voucher_id))
    return {'ok':True}


@router.post('/checkout/quote')
def quote(body:Checkout,user=Depends(require_user)):
    with connection() as db:
        db.execute('BEGIN')
        return calculate(db,user['id'],body)


def serialize_order(db,row):
    data=dict(row)
    data['items']=[dict(r) for r in db.execute('SELECT * FROM order_items WHERE order_id=?',(row['id'],))]
    return data


@router.get('/orders')
def orders(user=Depends(require_user)):
    with connection() as db:
        return [serialize_order(db,r) for r in db.execute('SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 100',(user['id'],))]


@router.post('/orders',status_code=201)
def place(body:OrderCreate,user=Depends(require_user)):
    fingerprint=hashlib.sha256(json.dumps(body.model_dump(exclude={'idempotency_key'}),sort_keys=True).encode()).hexdigest()
    with connection(write=True) as db:
        previous=db.execute('SELECT * FROM orders WHERE user_id=? AND idempotency_key=?',(user['id'],body.idempotency_key)).fetchone()
        if previous:
            if previous['request_hash']!=fingerprint:
                raise HTTPException(409,'Mã yêu cầu đã được dùng với nội dung khác.')
            return serialize_order(db,previous)
        bill=calculate(db,user['id'],body)
        if body.quote_token!=bill['quote_token']:
            raise HTTPException(409,'Sản phẩm, địa chỉ hoặc ưu đãi đã thay đổi. Vui lòng kiểm tra lại đơn trước khi đặt hàng.')
        if body.expected_total is not None and body.expected_total!=bill['total']:
            raise HTTPException(409,'Tổng thanh toán đã thay đổi. Vui lòng xem lại báo giá trước khi đặt hàng.')
        if body.payment_method=='ShopeePay':
            if not db.execute('UPDATE users SET wallet_balance=wallet_balance-? WHERE id=? AND wallet_balance>=?',(bill['total'],user['id'],bill['total'])).rowcount:
                raise HTTPException(409,'Số dư ví demo không đủ. Vui lòng chọn COD.')
        if bill['coin_discount']:
            if not db.execute('UPDATE users SET shopee_coins=shopee_coins-? WHERE id=? AND shopee_coins>=?',(bill['coin_discount'],user['id'],bill['coin_discount'])).rowcount:
                raise HTTPException(409,'Số dư Xu đã thay đổi. Vui lòng thử lại.')
        if bill['voucher_id']:
            if not db.execute("UPDATE user_vouchers SET status='used' WHERE user_id=? AND voucher_id=? AND status='available'",(user['id'],bill['voucher_id'])).rowcount:
                raise HTTPException(409,'Voucher đã được sử dụng.')
        address=bill['address'];code='SPX'+secrets.token_hex(6).upper()
        order_id=db.execute('''INSERT INTO orders(order_code,user_id,total_goods_amount,shipping_fee,voucher_discount,
            coin_discount,final_payment_amount,payment_method,recipient_name,recipient_phone,shipping_address,
            idempotency_key,request_hash,voucher_id,shipping_discount) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (code,user['id'],bill['subtotal'],bill['shipping_fee'],bill['voucher_discount'],bill['coin_discount'],bill['total'],
             body.payment_method,address['recipient_name'],address['phone'],address['detail']+', '+address['province_name'],
             body.idempotency_key,fingerprint,bill['voucher_id'],bill['shipping_discount'])).lastrowid
        for item in bill['items']:
            if not db.execute('UPDATE products SET stock=stock-?,sold_count=sold_count+? WHERE id=? AND stock>=?',
                              (item['quantity'],item['quantity'],item['id'],item['quantity'])).rowcount:
                raise HTTPException(409,'Tồn kho đã thay đổi. Vui lòng thử lại.')
            db.execute('''INSERT INTO order_items(order_id,product_id,quantity,unit_price,product_name,image_url,shop_name)
                VALUES (?,?,?,?,?,?,?)''',(order_id,item['id'],item['quantity'],item['price'],item['name'],item['image_url'],item['shop_name']))
            record_behavior(db,user,item,'purchase')
            if 'cart_item_id' in item:
                db.execute('DELETE FROM cart_items WHERE id=? AND user_id=?',(item['cart_item_id'],user['id']))
        db.execute("INSERT INTO notifications(user_id,title,content,type) VALUES (?,?,?,'order')",(user['id'],'Đặt hàng thành công',f'Đơn {code} đang chờ shop xác nhận. Theo dõi trong Đơn mua.'))
        db.execute('INSERT INTO audit_events(user_id,action,entity_id) VALUES (?,?,?)',(user['id'],'order.created',code))
        return serialize_order(db,db.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone())


@router.post('/orders/{order_id}/cancel')
def cancel(order_id:int,user=Depends(require_user)):
    with connection(write=True) as db:
        row=db.execute('SELECT * FROM orders WHERE id=? AND user_id=?',(order_id,user['id'])).fetchone()
        if not row:
            raise HTTPException(404,'Đơn hàng không tồn tại.')
        if row['order_status']=='Đã hủy':
            return {'ok':True}
        if row['order_status']!='Chờ xác nhận':
            raise HTTPException(409,'Chỉ có thể hủy đơn đang chờ xác nhận.')
        db.execute("UPDATE orders SET order_status='Đã hủy' WHERE id=?",(order_id,))
        db.execute('UPDATE users SET shopee_coins=shopee_coins+?,wallet_balance=wallet_balance+? WHERE id=?',
                   (row['coin_discount'],row['final_payment_amount'] if row['payment_method']=='ShopeePay' else 0,user['id']))
        if row['voucher_id']:
            db.execute("UPDATE user_vouchers SET status='available' WHERE user_id=? AND voucher_id=?",(user['id'],row['voucher_id']))
        for item in db.execute('SELECT * FROM order_items WHERE order_id=?',(order_id,)):
            db.execute('UPDATE products SET stock=stock+?,sold_count=MAX(0,sold_count-?) WHERE id=?',(item['quantity'],item['quantity'],item['product_id']))
        db.execute("INSERT INTO notifications(user_id,title,content,type) VALUES (?,?,?,'order')",(user['id'],'Đã hủy đơn hàng',f"Đơn {row['order_code']} đã được hủy. Tiền ví demo, Xu và voucher đã được hoàn lại nếu có."))
        db.execute('INSERT INTO audit_events(user_id,action,entity_id) VALUES (?,?,?)',(user['id'],'order.cancelled',row['order_code']))
    return {'ok':True}


@router.post('/orders/{order_id}/reorder')
def reorder(order_id:int,user=Depends(require_user)):
    with connection(write=True) as db:
        if not db.execute('SELECT 1 FROM orders WHERE id=? AND user_id=?',(order_id,user['id'])).fetchone():
            raise HTTPException(404,'Đơn hàng không tồn tại.')
        rows=db.execute('''SELECT p.*,i.quantity ordered_quantity,COALESCE(c.quantity,0) cart_quantity
            FROM order_items i JOIN products p ON p.id=i.product_id
            LEFT JOIN cart_items c ON c.product_id=p.id AND c.user_id=? WHERE i.order_id=?''',(user['id'],order_id)).fetchall()
        for item in rows:
            quantity=item['ordered_quantity']+item['cart_quantity']
            if quantity>min(item['stock'],99):
                raise HTTPException(409,f"{item['name']} không đủ tồn kho. Giỏ hàng chưa được thay đổi.")
            db.execute('''INSERT INTO cart_items(user_id,product_id,quantity) VALUES (?,?,?)
                ON CONFLICT(user_id,product_id) DO UPDATE SET quantity=excluded.quantity,is_selected=1''',
                (user['id'],item['id'],quantity))
            record_behavior(db,user,item,'add_to_cart')
    return {'ok':True}


@router.post('/orders/{order_id}/demo-advance',dependencies=[Depends(require_demo)])
def advance(order_id:int,user=Depends(require_user)):
    with connection(write=True) as db:
        row=db.execute('SELECT * FROM orders WHERE id=? AND user_id=?',(order_id,user['id'])).fetchone()
        if not row:
            raise HTTPException(404,'Đơn hàng không tồn tại.')
        status={'Chờ xác nhận':'Đang giao','Đang giao':'Đã giao'}.get(row['order_status'])
        if not status:
            raise HTTPException(409,'Đơn không thể chuyển trạng thái.')
        db.execute('UPDATE orders SET order_status=? WHERE id=?',(status,order_id))
        db.execute('INSERT INTO audit_events(user_id,action,entity_id) VALUES (?,?,?)',(user['id'],'demo.order.'+status,row['order_code']))
        db.execute("INSERT INTO notifications(user_id,title,content,type) VALUES (?,?,?,'order')",(user['id'],status,f"[Mô phỏng] Đơn {row['order_code']}: {status.lower()}."))
    return {'ok':True,'status':status}
