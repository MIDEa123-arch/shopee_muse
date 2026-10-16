"""One shipping rule shared by cart, checkout and recommendation context."""
from app import config


def shipping_groups(items,base_fee=0):
    groups={}
    for item in items:
        groups.setdefault(item['shop_name'],[]).append(item)
    result=[]
    for shop,rows in groups.items():
        subtotal=sum(row['price']*row['quantity'] for row in rows)
        eligible=all(row['is_freeship'] for row in rows)
        remaining=max(0,config.FREE_SHIPPING_THRESHOLD-subtotal) if eligible else None
        result.append({'shop_name':shop,'subtotal':subtotal,'eligible':eligible,
                       'remaining':remaining,'shipping_fee':base_fee,
                       'shipping_discount':base_fee if remaining==0 else 0,
                       'threshold':config.FREE_SHIPPING_THRESHOLD})
    return result
