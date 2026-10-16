import hashlib
from fastapi import APIRouter, Depends, HTTPException
from app import config
from app.seed_data import SAMPLE_PROFILES
from app.database import connection, public_product
from app.schemas import Address, Profile
from app.security import require_user, safe_user
from app.services.behavior import record_behavior

router=APIRouter(prefix='/api/account',tags=['account'])


def avatar_options():
    options=[]
    for index,profile in enumerate(SAMPLE_PROFILES):
        url=profile[3]
        filename=hashlib.sha256(url.split('?')[0].encode()).hexdigest()[:16]+'.jpg'
        local='/static/images/catalog/'+filename
        options.append({'label':f'Ảnh đại diện {index+1}','url':local if (config.ROOT/local.lstrip('/')).exists() else url})
    return options


@router.get('/avatar-options')
def avatars(user=Depends(require_user)):
    return avatar_options()


@router.put('/profile')
def profile(body:Profile,user=Depends(require_user)):
    avatar=body.avatar_url or user['avatar_url']
    if body.avatar_url and body.avatar_url not in {x['url'] for x in avatar_options()}|{user['avatar_url']}:
        raise HTTPException(422,'Vui lòng chọn ảnh đại diện có sẵn.')
    with connection(write=True) as db:
        db.execute('UPDATE users SET full_name=?,phone=?,gender=?,birth_year=?,avatar_url=? WHERE id=?',
                   (body.full_name.strip(),body.phone,body.gender,body.birth_year,avatar,user['id']))
        return safe_user(db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone())


@router.get('/addresses')
def addresses(user=Depends(require_user)):
    with connection() as db:
        return [dict(r) for r in db.execute('''SELECT a.*,p.name province_name FROM addresses a
            JOIN provinces p ON p.id=a.province_id WHERE user_id=? ORDER BY is_default DESC,a.id DESC''',(user['id'],))]


def save_address(db,body,user_id,address_id=None):
    if not db.execute('SELECT 1 FROM provinces WHERE id=?',(body.province_id,)).fetchone():
        raise HTTPException(422,'Tỉnh thành không hợp lệ.')
    if address_id and not db.execute('SELECT 1 FROM addresses WHERE id=? AND user_id=?',(address_id,user_id)).fetchone():
        raise HTTPException(404,'Không tìm thấy địa chỉ.')
    first=not db.execute('SELECT 1 FROM addresses WHERE user_id=?',(user_id,)).fetchone()
    current=db.execute('SELECT is_default FROM addresses WHERE id=? AND user_id=?',(address_id,user_id)).fetchone() if address_id else None
    default=body.is_default or first or bool(current and current['is_default'])
    if default:
        db.execute('UPDATE addresses SET is_default=0 WHERE user_id=?',(user_id,))
    values=(body.recipient_name.strip(),body.phone,body.province_id,body.detail.strip(),body.label,int(default))
    if address_id:
        db.execute('UPDATE addresses SET recipient_name=?,phone=?,province_id=?,detail=?,label=?,is_default=? WHERE id=? AND user_id=?',values+(address_id,user_id))
    else:
        address_id=db.execute('INSERT INTO addresses(recipient_name,phone,province_id,detail,label,is_default,user_id) VALUES (?,?,?,?,?,?,?)',values+(user_id,)).lastrowid
    return dict(db.execute('SELECT * FROM addresses WHERE id=?',(address_id,)).fetchone())


@router.post('/addresses',status_code=201)
def add_address(body:Address,user=Depends(require_user)):
    with connection(write=True) as db:
        return save_address(db,body,user['id'])


@router.put('/addresses/{address_id}')
def update_address(address_id:int,body:Address,user=Depends(require_user)):
    with connection(write=True) as db:
        return save_address(db,body,user['id'],address_id)


@router.delete('/addresses/{address_id}')
def delete_address(address_id:int,user=Depends(require_user)):
    with connection(write=True) as db:
        if not db.execute('DELETE FROM addresses WHERE id=? AND user_id=?',(address_id,user['id'])).rowcount:
            raise HTTPException(404,'Không tìm thấy địa chỉ.')
        if not db.execute('SELECT 1 FROM addresses WHERE user_id=? AND is_default=1',(user['id'],)).fetchone():
            db.execute('UPDATE addresses SET is_default=1 WHERE id=(SELECT id FROM addresses WHERE user_id=? ORDER BY id LIMIT 1)',(user['id'],))
    return {'ok':True}


@router.get('/notifications')
def notifications(user=Depends(require_user)):
    with connection() as db:
        return [dict(r) for r in db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100',(user['id'],))]


@router.post('/notifications/read')
def read_notifications(user=Depends(require_user)):
    with connection(write=True) as db:
        db.execute('UPDATE notifications SET is_read=1 WHERE user_id=?',(user['id'],))
    return {'ok':True}


@router.get('/wishlist')
def wishlist(user=Depends(require_user)):
    with connection() as db:
        return [public_product(r) for r in db.execute('SELECT p.* FROM products p JOIN wishlist w ON w.product_id=p.id WHERE w.user_id=? ORDER BY w.rowid DESC',(user['id'],))]


@router.put('/wishlist/{product_id}')
def toggle_wishlist(product_id:int,user=Depends(require_user)):
    with connection(write=True) as db:
        product=db.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone()
        if not product:
            raise HTTPException(404,'Sản phẩm không tồn tại.')
        if db.execute('DELETE FROM wishlist WHERE user_id=? AND product_id=?',(user['id'],product_id)).rowcount:
            return {'saved':False}
        db.execute('INSERT INTO wishlist VALUES (?,?)',(user['id'],product_id))
        record_behavior(db,user,product,'favorite')
        return {'saved':True}
