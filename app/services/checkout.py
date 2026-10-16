from datetime import datetime
import hashlib
import json
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.services.cart import cart_rows
from app.database import public_product
from app.services.shipping import shipping_groups
from app import config


def today():
    return datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()


def voucher_issue(db,voucher,user,subtotal,shipping_remaining):
    if voucher['end_date']<today():
        return 'Voucher đã hết hạn.'
    if subtotal<voucher['min_order_value']:
        return f"Đơn từ {voucher['min_order_value']:,}đ."
    if voucher['code'] in ('VOUCHERMUSE30K','TAOBAO30K') and db.execute("SELECT 1 FROM orders WHERE user_id=? AND order_status!='Đã hủy'",(user['id'],)).fetchone():
        return 'Chỉ áp dụng cho đơn hàng đầu tiên.'
    if voucher['code'] in ('MUSEVIP100K','TAOBAOVIP100K') and user['member_tier'] not in ('Vàng','Kim Cương'):
        return 'Dành cho thành viên Vàng và Kim Cương.'
    if voucher['discount_type']=='freeship' and shipping_remaining==0:
        return 'Đơn đã được miễn phí vận chuyển. Hãy giữ mã cho lần sau.'
    return None


def calculate(db,user_id,body):
    user=db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
    address=db.execute('''SELECT a.*,p.name province_name,p.shipping_base_fee FROM addresses a
        JOIN provinces p ON p.id=a.province_id WHERE a.id=? AND a.user_id=?''',(body.address_id,user_id)).fetchone()
    if not address:
        raise HTTPException(422,'Vui lòng chọn địa chỉ nhận hàng hợp lệ.')
    if body.buy_now:
        row=db.execute('''SELECT p.*,pr.name province_name FROM products p
            LEFT JOIN provinces pr ON pr.id=p.province_id WHERE p.id=?''',(body.buy_now.product_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Sản phẩm không tồn tại.')
        items=[{**public_product(row),'quantity':body.buy_now.quantity}]
    else:
        items=[i for i in cart_rows(db,user_id) if i['is_selected']]
    if not items:
        raise HTTPException(400,'Chọn ít nhất một sản phẩm để thanh toán.')
    for item in items:
        if item['quantity']>item['stock'] or item['stock']<=0:
            raise HTTPException(409,f"{item['name']} không đủ tồn kho.")
    subtotal=sum(i['price']*i['quantity'] for i in items)
    # Shipping is per shop, with a configurable demo tariff by destination province.
    groups=shipping_groups(items,address['shipping_base_fee'])
    shipping_fee=sum(g['shipping_fee'] for g in groups)
    shipping_discount=sum(g['shipping_discount'] for g in groups)
    available=[dict(v) for v in db.execute('''SELECT v.* FROM vouchers v JOIN user_vouchers uv ON uv.voucher_id=v.id
        WHERE uv.user_id=? AND uv.status='available' ORDER BY v.id''',(user_id,))]
    for v in available:
        v['reason']=voucher_issue(db,v,user,subtotal,shipping_fee-shipping_discount)
        v['eligible']=v['reason'] is None
    voucher_discount=0;voucher=None
    if body.voucher_code.strip():
        voucher=db.execute('''SELECT v.* FROM vouchers v JOIN user_vouchers uv ON uv.voucher_id=v.id
            WHERE v.code=? AND uv.user_id=? AND uv.status='available' ''',(body.voucher_code.strip().upper(),user_id)).fetchone()
        if not voucher or voucher['end_date']<today():
            raise HTTPException(400,'Voucher không tồn tại, chưa được lưu, đã dùng hoặc hết hạn.')
        issue=voucher_issue(db,voucher,user,subtotal,shipping_fee-shipping_discount)
        if issue:
            raise HTTPException(400,issue)
        amount=voucher['discount_value']
        if voucher['discount_type']=='freeship':
            shipping_discount=min(shipping_fee,shipping_discount+amount)
        else:
            voucher_discount=subtotal*amount//100 if voucher['discount_type']=='percentage' else amount
            voucher_discount=min(subtotal,voucher_discount,voucher['max_discount_amount'] or voucher_discount)
    coin_discount=min(user['shopee_coins'],25000,max(0,subtotal-voucher_discount)) if body.use_coins else 0
    total=max(0,subtotal+shipping_fee-shipping_discount-voucher_discount-coin_discount)
    if body.payment_method=='ShopeePay' and not config.DEMO_MODE:
        raise HTTPException(503,'Thanh toán ví chưa được kết nối với nhà cung cấp.')
    bill={'items':items,'address':dict(address),'subtotal':subtotal,'shipping_fee':shipping_fee,
            'shipping_discount':shipping_discount,'voucher_discount':voucher_discount,'coin_discount':coin_discount,
            'total':total,'voucher_id':voucher['id'] if voucher else None,'shop_count':len(groups),
            'shipping_groups':groups,'available_vouchers':available,
            'payment_method':body.payment_method,'wallet_balance':user['wallet_balance'],'demo_payment':config.DEMO_MODE}
    # Bind approval to the actual goods, quantities, delivery address and every money component.
    # Equal totals alone cannot detect a different product or a changed address in another tab.
    snapshot={'user_id':user_id,'buy_now':bool(body.buy_now),'address':dict(address),
              'items':[{k:i[k] for k in ('id','quantity','price','shop_name','name')} for i in items],
              **{k:bill[k] for k in ('subtotal','shipping_fee','shipping_discount','voucher_discount',
                                    'coin_discount','total','voucher_id','payment_method')}}
    bill['quote_token']=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()
    return bill
