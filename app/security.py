import hashlib
import hmac
import re
import secrets
import time

from fastapi import Depends, HTTPException, Request, Response
from app import config
from app.database import connection


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"


def verify_password(password, encoded):
    if encoded.startswith('pbkdf2_sha256$'):
        _, rounds, salt, digest = encoded.split('$')
        value = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(digest, value)
    # Migrate existing demo hashes on successful login.
    return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), encoded)


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def create_session(db, response: Response, user_id):
    token = secrets.token_urlsafe(32)
    db.execute('DELETE FROM sessions WHERE expires_at<?', (time.time(),))
    db.execute('INSERT INTO sessions VALUES (?,?,?)', (token_hash(token), user_id, time.time()+config.SESSION_SECONDS))
    response.set_cookie('muse_session', token, httponly=True, secure=config.SECURE_COOKIES,
                        samesite='strict', max_age=config.SESSION_SECONDS, path='/')


def current_user(request: Request):
    token = request.cookies.get('muse_session')
    if not token:
        return None
    with connection() as db:
        user = db.execute('''SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id
            WHERE s.token_hash=? AND s.expires_at>?''', (token_hash(token), time.time())).fetchone()
        return dict(user) if user else None


def require_user(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, 'Vui lòng đăng nhập để tiếp tục.')
    return user


def require_demo():
    if not config.DEMO_MODE:
        raise HTTPException(404, 'Chức năng không khả dụng.')


def safe_user(user):
    if not user:
        return None
    data = {k: v for k, v in dict(user).items() if k not in ('password_hash','raw_user_id')}
    if config.DEMO_MODE:
        data['raw_user_id'] = str(user['raw_user_id']) if user['raw_user_id'] is not None else None
    return data


def check_email(value):
    value = value.strip().lower()
    if len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise HTTPException(422, 'Email không hợp lệ.')
    return value


def rate_limit(db, request, kind, limit=10):
    key = f"{kind}:{request.client.host if request.client else 'local'}"
    now = time.time()
    db.execute('DELETE FROM auth_attempts WHERE created_at<?', (now-900,))
    if db.execute('SELECT COUNT(*) FROM auth_attempts WHERE key=? AND created_at>?', (key,now-900)).fetchone()[0]>=limit:
        raise HTTPException(429,'Bạn thao tác quá nhiều lần. Vui lòng thử lại sau 15 phút.')
    db.execute('INSERT INTO auth_attempts VALUES (?,?)', (key,now))
