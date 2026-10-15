from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.services.cart import cart_rows
from app import config


def today():
    return datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()


def calculate(db,user_id,body):
    user=db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
    address=db.execute('''SELECT a.*,p.name province_name,p.shipping_base_fee FROM addresses a
        JOIN provinces p ON p.id=a.province_id WHERE a.id=? AND a.user_id=?''',(body.address_id,user_id)).fetchone()
    if not address:
        raise HTTPException(422,'Vui lòng chọn địa chỉ nhận hàng hợp lệ.')
    items=[i for i in cart_rows(db,user_id) if i['is_selected']]
    if not items:
        raise HTTPException(400,'Chọn ít nhất một sản phẩm để thanh toán.')
    for item in items:
        if item['quantity']>item['stock'] or item['stock']<=0:
            raise HTTPException(409,f"{item['name']} không đủ tồn kho.")
    subtotal=sum(i['price']*i['quantity'] for i in items)
    # Shipping is per shop, with a configurable demo tariff by destination province.
    shops={i['shop_name'] for i in items}
    shipping_fee=address['shipping_base_fee']*len(shops)
    shipping_discount=shipping_fee if subtotal>=config.FREE_SHIPPING_THRESHOLD and all(i['is_freeship'] for i in items) else 0
    voucher_discount=0;voucher=None
    if body.voucher_code.strip():
        voucher=db.execute('''SELECT v.* FROM vouchers v JOIN user_vouchers uv ON uv.voucher_id=v.id
            WHERE v.code=? AND uv.user_id=? AND uv.status='available' ''',(body.voucher_code.strip().upper(),user_id)).fetchone()
        if not voucher or voucher['end_date']<today():
            raise HTTPException(400,'Voucher không tồn tại, chưa được lưu, đã dùng hoặc hết hạn.')
        if subtotal<voucher['min_order_value']:
            raise HTTPException(400,f"Voucher áp dụng cho đơn từ {voucher['min_order_value']:,}đ.")
        if voucher['code']=='VOUCHERMUSE30K' and db.execute("SELECT 1 FROM orders WHERE user_id=? AND order_status!='Đã hủy'",(user_id,)).fetchone():
            raise HTTPException(400,'Voucher chỉ áp dụng cho đơn hàng đầu tiên.')
        if voucher['code']=='MUSEVIP100K' and user['member_tier'] not in ('Vàng','Kim Cương'):
            raise HTTPException(400,'Voucher dành cho thành viên Vàng và Kim Cương.')
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
    return {'items':items,'address':dict(address),'subtotal':subtotal,'shipping_fee':shipping_fee,
            'shipping_discount':shipping_discount,'voucher_discount':voucher_discount,'coin_discount':coin_discount,
            'total':total,'voucher_id':voucher['id'] if voucher else None,'shop_count':len(shops),
            'free_shipping_remaining':max(0,config.FREE_SHIPPING_THRESHOLD-subtotal),
            'payment_method':body.payment_method,'wallet_balance':user['wallet_balance'],'demo_payment':config.DEMO_MODE}
