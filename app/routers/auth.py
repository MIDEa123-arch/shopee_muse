import secrets
import sqlite3
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import config
from app.database import connection
from app.schemas import Login, Register
from app.security import (check_email,create_session,current_user,hash_password,
    rate_limit,require_demo,require_user,safe_user,token_hash,verify_password)

router = APIRouter(prefix='/api/auth',tags=['auth'])


@router.get('/me')
def me(user=Depends(current_user)):
    return {'user':safe_user(user),'demo_mode':config.DEMO_MODE}


@router.post('/login')
def login(body: Login, request: Request, response: Response):
    email = check_email(body.email)
    with connection(write=True) as db:
        rate_limit(db,request,'login')
    with connection(write=True) as db:
        user=db.execute('SELECT * FROM users WHERE lower(email)=?',(email,)).fetchone()
        if not user or not verify_password(body.password,user['password_hash']):
            raise HTTPException(401,'Email hoặc mật khẩu chưa chính xác.')
        if not user['password_hash'].startswith('pbkdf2_'):
            db.execute('UPDATE users SET password_hash=? WHERE id=?',(hash_password(body.password),user['id']))
        create_session(db,response,user['id'])
        return {'user':safe_user(user)}


@router.post('/register',status_code=201)
def register(body: Register,request: Request,response: Response):
    email=check_email(body.email)
    with connection(write=True) as db:
        rate_limit(db,request,'register',5)
    try:
        with connection(write=True) as db:
            uid=db.execute('''INSERT INTO users(full_name,email,phone,password_hash,member_tier,shopee_coins,wallet_balance,gender,birth_year)
                VALUES (?,?,?,?,'Thành viên Mới',0,0,?,?)''',(body.full_name.strip(),email,body.phone,hash_password(body.password),body.gender or 'Khác',body.birth_year)).lastrowid
            db.execute('''INSERT INTO addresses(user_id,recipient_name,phone,province_id,detail,is_default)
                VALUES (?,?,?,1,'123 Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1',1)''',
                (uid, body.full_name.strip(), body.phone))
            welcome_vouchers = db.execute("SELECT id FROM vouchers WHERE code IN ('VOUCHERMUSE30K', 'TAOBAO30K', 'FREESHIP')").fetchall()
            for v in welcome_vouchers:
                db.execute("INSERT OR IGNORE INTO user_vouchers(user_id, voucher_id, status) VALUES (?, ?, 'available')", (uid, v[0]))
            db.execute("INSERT INTO notifications(user_id,title,content,type) VALUES (?,'Chào mừng bạn!','Tài khoản đã sẵn sàng với địa chỉ nhận hàng và ưu đãi chào bạn mới.','system')",(uid,))
            create_session(db,response,uid)
            return {'user':safe_user(db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())}
    except sqlite3.IntegrityError:
        raise HTTPException(409,'Email này đã được sử dụng.')


@router.post('/logout')
def logout(request:Request,response:Response):
    with connection(write=True) as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(request.cookies.get('muse_session','')),))
    response.delete_cookie('muse_session',path='/')
    return {'ok':True}


@router.get('/demo-profiles',dependencies=[Depends(require_demo)])
def demo_profiles():
    with connection() as db:
        return [dict(r) for r in db.execute('SELECT id,full_name,avatar_url,member_tier FROM users WHERE raw_user_id IS NOT NULL ORDER BY id LIMIT 8')]


class DemoLogin(BaseModel):
    user_id:int


@router.post('/demo-login',dependencies=[Depends(require_demo)])
def demo_login(body:DemoLogin,response:Response):
    with connection(write=True) as db:
        user=db.execute('SELECT * FROM users WHERE id=? AND raw_user_id IS NOT NULL',(body.user_id,)).fetchone()
        if not user:
            raise HTTPException(404,'Không tìm thấy hồ sơ demo.')
        create_session(db,response,user['id'])
        return {'user':safe_user(user)}


class Forgot(BaseModel):
    email:str=Field(max_length=254)


@router.post('/forgot-password')
def forgot(body:Forgot,request:Request):
    if not config.DEMO_MODE:
        raise HTTPException(503,'Kênh gửi email khôi phục chưa được cấu hình. Vui lòng liên hệ hỗ trợ.')
    with connection(write=True) as db:
        rate_limit(db,request,'reset',5)
        uid=db.execute('SELECT id FROM users WHERE lower(email)=?',(check_email(body.email),)).fetchone()
        challenge=secrets.token_urlsafe(32)
        db.execute('DELETE FROM reset_challenges WHERE expires_at<?',(time.time(),))
        if uid:
            db.execute('DELETE FROM reset_challenges WHERE user_id=?',(uid['id'],))
        db.execute('INSERT INTO reset_challenges(id,user_id,code_hash,expires_at) VALUES (?,?,?,?)',
            (challenge,uid['id'] if uid else None,token_hash('888999'),time.time()+300))
        return {'challenge_id':challenge,'message':'Nếu email tồn tại, bạn có thể đặt lại mật khẩu.','demo_code':'888999','expires_in':300}


class Reset(BaseModel):
    challenge_id:str=Field(max_length=100)
    code:str=Field(max_length=10)
    password:str=Field(min_length=8,max_length=128)


@router.post('/reset-password')
def reset(body:Reset,request:Request):
    with connection(write=True) as db:
        rate_limit(db,request,'reset-verify',10)
        row=db.execute('SELECT * FROM reset_challenges WHERE id=?',(body.challenge_id,)).fetchone()
        valid=bool(row and row['user_id'] and row['expires_at']>time.time() and row['attempts']<5
                   and secrets.compare_digest(row['code_hash'],token_hash(body.code)))
        if row:
            db.execute('UPDATE reset_challenges SET attempts=attempts+1 WHERE id=?',(body.challenge_id,))
        if valid:
            db.execute('UPDATE users SET password_hash=? WHERE id=?',(hash_password(body.password),row['user_id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(row['user_id'],))
            db.execute('DELETE FROM reset_challenges WHERE user_id=?',(row['user_id'],))
    if not valid:
        raise HTTPException(400,'Mã OTP không đúng, hết hạn hoặc đã được sử dụng.')
    return {'ok':True}


class ChangePassword(BaseModel):
    current_password:str=Field(max_length=128)
    new_password:str=Field(min_length=8,max_length=128)


@router.post('/password')
def change_password(body:ChangePassword,response:Response,user=Depends(require_user)):
    if not verify_password(body.current_password,user['password_hash']):
        raise HTTPException(400,'Mật khẩu hiện tại chưa chính xác.')
    with connection(write=True) as db:
        db.execute('UPDATE users SET password_hash=? WHERE id=?',(hash_password(body.new_password),user['id']))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        create_session(db,response,user['id'])
    return {'ok':True}
