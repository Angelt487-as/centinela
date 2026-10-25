"""Server-side sessions. Only hashes of opaque session/challenge cookies are persisted."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from typing import Literal

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from .database import audit, connection
from .files import now

COOKIE = 'c360_session'
LOGIN_COOKIE = 'c360_login'
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
PUBLIC_PATHS = {'/api/health', '/api/auth/csrf', '/api/auth/login'}
ROLE = Literal['administrador', 'analista']
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16, type=Type.ID)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))
HASH_SLOTS = threading.BoundedSemaphore(2)
USERNAME = re.compile(r'^[a-z0-9][a-z0-9_.-]{2,49}$')
router = APIRouter(prefix='/api')


def clock():
    return int(time.time())


def allowed_origins():
    defaults = 'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173,http://127.0.0.1:8000'
    return [v.strip().rstrip('/') for v in os.environ.get('CENTINELA_ALLOWED_ORIGINS', defaults).split(',') if v.strip()]


def secure_cookie(request):
    return request.url.scheme == 'https' or os.environ.get('CENTINELA_COOKIE_SECURE', '').lower() in {'1', 'true', 'yes'}


def lifetime():
    return max(60, min(int(os.environ.get('CENTINELA_SESSION_SECONDS', '28800')), 86400))


def idle_lifetime():
    return max(60, min(int(os.environ.get('CENTINELA_IDLE_SECONDS', '1800')), lifetime()))


def digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def csrf_for(token, context='session'):
    return hmac.new(token.encode('ascii'), ('centinela-csrf-v1:' + context).encode('ascii'), hashlib.sha256).hexdigest()


def valid_token(token):
    return bool(token and re.fullmatch(r'[a-zA-Z0-9_-]{43}', token))


def set_cookie(response, request, name, value, seconds):
    response.set_cookie(name, value, max_age=seconds, path='/', httponly=True,
                        secure=secure_cookie(request), samesite='strict')


def clear_cookie(response, request, name=COOKIE):
    response.delete_cookie(name, path='/', httponly=True, secure=secure_cookie(request), samesite='strict')


def public_user(row):
    return {k: bool(row[k]) if k == 'active' else row[k]
            for k in ('id', 'username', 'role', 'active', 'created_at', 'last_login')}


def require_csrf(request, token, context='session'):
    supplied = request.headers.get('x-csrf-token', '')
    if not valid_token(token) or len(supplied) != 64 or not hmac.compare_digest(supplied, csrf_for(token, context)):
        raise HTTPException(403, 'La solicitud no pudo verificarse. Recarga la página y vuelve a intentar.')


def authenticate_request(request):
    """Default-deny protection for every API path, including new and unknown paths."""
    path = request.url.path
    if path in PUBLIC_PATHS or request.method == 'OPTIONS':
        return
    if not (path.startswith('/api') or path in {'/docs', '/redoc', '/openapi.json', '/docs/oauth2-redirect'}):
        return
    token = request.cookies.get(COOKIE, '')
    if not valid_token(token):
        raise HTTPException(401, 'Inicia sesión para acceder a Centinela 360.')
    current = clock()
    with connection() as db:
        row = db.execute('''SELECT s.token_hash,s.expires_at,s.last_seen_at,u.* FROM sessions s
                            JOIN users u ON s.user_id=u.id WHERE s.token_hash=?''', (digest(token),)).fetchone()
        if not row or not row['active'] or row['expires_at'] <= current or row['last_seen_at'] + idle_lifetime() <= current:
            if row:
                db.execute('DELETE FROM sessions WHERE token_hash=?', (row['token_hash'],))
            # Commit removal before raising.
            user = None
        else:
            user = public_user(row)
            db.execute('UPDATE sessions SET last_seen_at=? WHERE token_hash=?', (current, row['token_hash']))
    if not user:
        raise HTTPException(401, 'Tu sesión terminó. Inicia sesión nuevamente.')
    request.state.user = user
    request.state.session_hash = digest(token)
    request.state.csrf_token = csrf_for(token)
    request.state.session_deadline = min(row['expires_at'], current + idle_lifetime())
    if request.method not in SAFE_METHODS:
        require_csrf(request, token)


def current_user(request: Request):
    user = getattr(request.state, 'user', None)
    if not user:
        raise HTTPException(401, 'Inicia sesión para continuar.')
    return user


def administrator(user=Depends(current_user)):
    if user['role'] != 'administrador':
        raise HTTPException(403, 'Esta función está reservada para administradores.')
    return user


def validate_password(password):
    if not 12 <= len(password) <= 128 or not password.strip() or '\x00' in password:
        raise HTTPException(422, 'La contraseña debe tener entre 12 y 128 caracteres. Puedes usar una frase larga.')
    return password


def normalize_username(username):
    username = username.strip().lower()
    if not USERNAME.fullmatch(username):
        raise HTTPException(422, 'Usa un usuario de 3 a 50 caracteres: letras sin acentos, números, punto, guion o guion bajo.')
    return username


def hash_password(password):
    validate_password(password)
    with HASH_SLOTS:
        return HASHER.hash(password)


def verify_password(encoded, password):
    try:
        return HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def reserve_attempt(request, username):
    current = clock()
    address = request.client.host if request.client else 'unknown'
    buckets = [('ip:' + digest(address), 100), ('user:' + digest(username), 5)]
    retry = 0
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM auth_limits WHERE window_started<=?', (current - 900,))
        for bucket, limit in buckets:
            row = db.execute('SELECT * FROM auth_limits WHERE bucket=?', (bucket,)).fetchone()
            if row and row['attempts'] >= limit:
                retry = max(retry, row['window_started'] + 900 - current)
        if not retry:
            for bucket, _ in buckets:
                db.execute('''INSERT INTO auth_limits VALUES(?,1,?) ON CONFLICT(bucket)
                              DO UPDATE SET attempts=attempts+1''', (bucket, current))
    if retry:
        raise HTTPException(429, 'Demasiados intentos de acceso. Espera unos minutos y vuelve a intentar.', headers={'Retry-After': str(retry)})


@router.get('/auth/csrf')
def login_challenge(request: Request, response: Response):
    token = request.cookies.get(LOGIN_COOKIE, '')
    current = clock()
    with connection() as db:
        db.execute('DELETE FROM login_challenges WHERE expires_at<=?', (current,))
        existing = db.execute('SELECT expires_at FROM login_challenges WHERE token_hash=?', (digest(token),)).fetchone() if valid_token(token) else None
        if not existing:
            # Bound anonymous challenge storage without evicting valid browser sessions.
            if db.execute('SELECT COUNT(*) FROM login_challenges').fetchone()[0] >= 5000:
                raise HTTPException(429, 'Intenta iniciar sesión más tarde.')
            token = secrets.token_urlsafe(32)
            db.execute('INSERT INTO login_challenges VALUES(?,?)', (digest(token), current + 600))
        setup = not db.execute('SELECT id FROM users LIMIT 1').fetchone()
    set_cookie(response, request, LOGIN_COOKIE, token, 600)
    return {'csrf_token': csrf_for(token, 'login'), 'setup_required': setup}


class LoginInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=1, max_length=1024)


@router.post('/auth/login')
def login(value: LoginInput, request: Request, response: Response):
    challenge = request.cookies.get(LOGIN_COOKIE, '')
    require_csrf(request, challenge, 'login')
    with connection() as db:
        issued = db.execute('SELECT expires_at FROM login_challenges WHERE token_hash=?', (digest(challenge),)).fetchone()
    if not issued or issued['expires_at'] <= clock():
        raise HTTPException(403, 'La solicitud de acceso caducó. Recarga la página e intenta nuevamente.')
    username = value.username.strip().lower()
    reserve_attempt(request, username)
    if not HASH_SLOTS.acquire(blocking=False):
        raise HTTPException(429, 'El servicio de acceso está ocupado. Intenta nuevamente en unos segundos.', headers={'Retry-After': '2'})
    try:
        with connection() as db:
            row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        password = value.password.get_secret_value()
        matched = verify_password(row['password_hash'] if row else DUMMY_HASH, password)
        if not matched or not row or not row['active']:
            raise HTTPException(401, 'Usuario o contraseña incorrectos.')
        replacement = HASHER.hash(password) if HASHER.check_needs_rehash(row['password_hash']) else None
    finally:
        HASH_SLOTS.release()
    token = secrets.token_urlsafe(32)
    current = clock()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        # Recheck state and hash after verification to prevent racing a password reset/deactivation.
        fresh = db.execute('SELECT * FROM users WHERE id=?', (row['id'],)).fetchone()
        if not fresh or not fresh['active'] or fresh['password_hash'] != row['password_hash']:
            raise HTTPException(401, 'Usuario o contraseña incorrectos.')
        old = request.cookies.get(COOKIE, '')
        if valid_token(old):
            db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(old),))
        db.execute('DELETE FROM sessions WHERE expires_at<=? OR last_seen_at<=?', (current, current - idle_lifetime()))
        db.execute('INSERT INTO sessions VALUES(?,?,?,?,?)', (digest(token), row['id'], current, current, current + lifetime()))
        db.execute('UPDATE users SET last_login=? WHERE id=?', (now(), row['id']))
        if replacement:
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (replacement, row['id']))
        db.execute('DELETE FROM auth_limits WHERE bucket=?', ('user:' + digest(username),))
        db.execute('DELETE FROM login_challenges WHERE token_hash=?', (digest(challenge),))
        audit(db, 'sesion_iniciada', row['id'], now())
        user = public_user(db.execute('SELECT * FROM users WHERE id=?', (row['id'],)).fetchone())
    set_cookie(response, request, COOKIE, token, lifetime())
    clear_cookie(response, request, LOGIN_COOKIE)
    return {'user': user, 'csrf_token': csrf_for(token), 'expires_at': min(current + lifetime(), current + idle_lifetime())}


@router.get('/auth/session')
def session(request: Request, user=Depends(current_user)):
    return {'user': user, 'csrf_token': request.state.csrf_token, 'expires_at': request.state.session_deadline}


@router.post('/auth/logout')
def logout(request: Request, response: Response, user=Depends(current_user)):
    with connection() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?', (request.state.session_hash,))
        audit(db, 'sesion_cerrada', user['id'], now())
    clear_cookie(response, request)
    clear_cookie(response, request, LOGIN_COOKIE)
    return {'message': 'Sesión cerrada.'}


class UserCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=50)
    password: SecretStr = Field(min_length=12, max_length=128)
    role: ROLE = 'analista'
    active: bool = True


def create_user(username, password, role='analista', active=True, *, initial_only=False, actor_id=None):
    username = normalize_username(username)
    if role not in {'administrador', 'analista'}:
        raise HTTPException(422, 'Rol no válido.')
    encoded = hash_password(password)
    id_ = uuid.uuid4().hex
    try:
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if initial_only and db.execute('SELECT id FROM users LIMIT 1').fetchone():
                raise HTTPException(409, 'El administrador inicial ya está configurado. Usa la administración de usuarios.')
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,?,NULL)', (id_, username, encoded, role, int(active), now()))
            audit(db, 'usuario_creado', id_, now(), {'actor_id': actor_id, 'role': role})
            return public_user(db.execute('SELECT * FROM users WHERE id=?', (id_,)).fetchone())
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'Ese nombre de usuario ya está registrado.') from None


@router.get('/users')
def users(user=Depends(administrator)):
    with connection() as db:
        return {'items': [public_user(r) for r in db.execute('SELECT * FROM users ORDER BY created_at,username')]}


@router.post('/users')
def add_user(value: UserCreate, user=Depends(administrator)):
    return create_user(value.username, value.password.get_secret_value(), value.role, value.active, actor_id=user['id'])


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: ROLE
    active: bool
    password: SecretStr | None = Field(default=None, min_length=12, max_length=128)


@router.put('/users/{user_id}')
def update_user(user_id: str, value: UserUpdate, actor=Depends(administrator)):
    encoded = hash_password(value.password.get_secret_value()) if value.password else None
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'El usuario no existe.')
        if row['active'] and row['role'] == 'administrador' and (not value.active or value.role != 'administrador'):
            count = db.execute("SELECT COUNT(*) FROM users WHERE active=1 AND role='administrador'").fetchone()[0]
            if count <= 1:
                raise HTTPException(409, 'Debe permanecer al menos un administrador activo.')
        db.execute('UPDATE users SET role=?,active=? WHERE id=?', (value.role, int(value.active), user_id))
        if encoded:
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (encoded, user_id))
        if encoded or value.role != row['role'] or value.active != bool(row['active']):
            db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
        audit(db, 'usuario_actualizado', user_id, now(), {'actor_id': actor['id'], 'sessions_revoked': bool(encoded or value.role != row['role'] or value.active != bool(row['active']))})
        return public_user(db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone())


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(min_length=12, max_length=128)


@router.post('/auth/password')
def change_password(value: PasswordChange, request: Request, response: Response, user=Depends(current_user)):
    reserve_attempt(request, user['username'])
    with connection() as db:
        row = db.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
    with HASH_SLOTS:
        matched = verify_password(row['password_hash'], value.current_password.get_secret_value())
    if not matched:
        raise HTTPException(400, 'No se pudo cambiar la contraseña. Revisa los datos e intenta otra vez.')
    encoded = hash_password(value.new_password.get_secret_value())
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT password_hash FROM users WHERE id=?', (user['id'],)).fetchone()
        if not current or current['password_hash'] != row['password_hash']:
            raise HTTPException(409, 'Los datos de acceso cambiaron. Inicia sesión de nuevo.')
        db.execute('UPDATE users SET password_hash=? WHERE id=?', (encoded, user['id']))
        db.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
        db.execute('DELETE FROM auth_limits WHERE bucket=?', ('user:' + digest(user['username']),))
        audit(db, 'contrasena_actualizada', user['id'], now())
    clear_cookie(response, request)
    return {'message': 'Contraseña actualizada. Inicia sesión nuevamente.'}
