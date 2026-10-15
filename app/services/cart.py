from app.database import public_product


def cart_rows(db,user_id):
    return [public_product(r) for r in db.execute('''SELECT p.*,c.id cart_item_id,c.quantity,c.is_selected,
        pr.name province_name FROM cart_items c JOIN products p ON p.id=c.product_id
        LEFT JOIN provinces pr ON pr.id=p.province_id WHERE c.user_id=? ORDER BY c.id DESC''',(user_id,))]
