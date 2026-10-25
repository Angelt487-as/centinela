import hashlib
import secrets

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import auth
from backend.app.database import connection, initialize
from backend.app.main import app
from conftest import sign_in


def attempt(client, username, password):
    token = client.get('/api/auth/csrf').json()['csrf_token']
    return client.post('/api/auth/login', json={'username': username, 'password': password}, headers={'X-CSRF-Token': token})


def test_every_private_endpoint_is_protected(anonymous_client):
    for route in app.routes:
        path = getattr(route, 'path', '')
        if path in auth.PUBLIC_PATHS or not (path.startswith('/api') or path in {'/docs', '/redoc', '/openapi.json', '/docs/oauth2-redirect'}):
            continue
        for method in getattr(route, 'methods', {'GET'}) - {'HEAD', 'OPTIONS'}:
            response = anonymous_client.request(method, path)
            assert response.status_code == 401, (method, path)
            assert response.headers['cache-control'] == 'no-store'


def test_bootstrap_only_local_and_existing_data_preserved(anonymous_client):
    assert anonymous_client.get('/api/auth/csrf').json()['setup_required']
    assert anonymous_client.post('/api/auth/register', json={}).status_code == 401
    password = secrets.token_urlsafe(24)
    user = auth.create_user('inicial', password, 'administrador', initial_only=True)
    assert user['role'] == 'administrador'
    with connection() as db:
        encoded = db.execute('SELECT password_hash FROM users').fetchone()[0]
        assert encoded.startswith('$argon2id$') and password not in encoded
        db.execute("INSERT INTO sources(id,title,url,description,observed_at,notes,created_at) VALUES('preservar','Fuente existente','https://example.org','','2026-10-24','','2026-10-24')")
    initialize()
    with connection() as db:
        assert db.execute("SELECT title FROM sources WHERE id='preservar'").fetchone()[0] == 'Fuente existente'
    try:
        auth.create_user('otro', secrets.token_urlsafe(24), 'administrador', initial_only=True)
        assert False
    except HTTPException as error:
        assert error.status_code == 409


def test_login_cookie_hash_only_rotation_logout(anonymous_client, accounts):
    response = sign_in(anonymous_client, accounts['admin']['username'].upper(), accounts['admin_password'])
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Path=/' in cookie and 'Domain=' not in cookie
    raw = anonymous_client.cookies.get(auth.COOKIE)
    with connection() as db:
        row = db.execute('SELECT * FROM sessions').fetchone()
        assert row['token_hash'] == hashlib.sha256(raw.encode()).hexdigest()
        assert raw not in str(dict(row))
        assert db.execute('SELECT last_login FROM users WHERE id=?', (accounts['admin']['id'],)).fetchone()[0]
    session = anonymous_client.get('/api/auth/session').json()
    assert session['user']['role'] == 'administrador' and session['csrf_token']
    assert 'password_hash' not in str(session)
    old = raw
    sign_in(anonymous_client, accounts['admin']['username'], accounts['admin_password'])
    assert anonymous_client.cookies.get(auth.COOKIE) != old
    with TestClient(app) as stale:
        stale.cookies.set(auth.COOKIE, old)
        assert stale.get('/api/overview').status_code == 401
    assert anonymous_client.post('/api/auth/logout').status_code == 200
    assert anonymous_client.get('/api/events/export').status_code == 401


def test_generic_credentials_and_inactive_response(anonymous_client, accounts):
    wrong = secrets.token_urlsafe(24)
    bad_user = attempt(anonymous_client, 'nadie-' + secrets.token_hex(4), wrong)
    bad_password = attempt(anonymous_client, accounts['admin']['username'], wrong)
    with connection() as db:
        db.execute('UPDATE users SET active=0 WHERE id=?', (accounts['analyst']['id'],))
    inactive = attempt(anonymous_client, accounts['analyst']['username'], accounts['analyst_password'])
    assert [r.status_code for r in (bad_user, bad_password, inactive)] == [401, 401, 401]
    assert bad_user.json() == bad_password.json() == inactive.json()


def test_csrf_login_and_all_mutations(anonymous_client, accounts):
    assert anonymous_client.post('/api/auth/login', json={'username': accounts['admin']['username'], 'password': accounts['admin_password']}).status_code == 403
    sign_in(anonymous_client, accounts['admin']['username'], accounts['admin_password'])
    good = anonymous_client.headers.pop('X-CSRF-Token')
    for path in ['/api/dossiers/demo', '/api/sources', '/api/users', '/api/auth/logout']:
        assert anonymous_client.post(path, json={}).status_code == 403
    anonymous_client.headers['X-CSRF-Token'] = good
    assert anonymous_client.post('/api/dossiers/demo', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert anonymous_client.post('/api/dossiers/demo', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert anonymous_client.post('/api/dossiers/demo').status_code == 200


def test_roles_users_revocation_and_last_admin(client, accounts):
    csrf = client.headers['X-CSRF-Token']
    listed = client.get('/api/users').json()['items']
    assert len(listed) == 2 and all('password_hash' not in row for row in listed)
    duplicate = client.post('/api/users', json={'username': accounts['analyst']['username'].upper(), 'password': secrets.token_urlsafe(24)})
    assert duplicate.status_code == 409
    with TestClient(app) as analyst:
        sign_in(analyst, accounts['analyst']['username'], accounts['analyst_password'])
        assert analyst.get('/api/overview').status_code == 200
        assert analyst.get('/api/users').status_code == 403
        assert analyst.post('/api/users', json={'username': 'visitante', 'password': secrets.token_urlsafe(24), 'role': 'administrador'}).status_code == 403
        assert analyst.put('/api/users/' + accounts['admin']['id'], json={'role': 'analista', 'active': False}).status_code == 403
        result = client.put('/api/users/' + accounts['analyst']['id'], json={'role': 'analista', 'active': False})
        assert result.status_code == 200
        assert analyst.get('/api/overview').status_code == 401
    assert client.put('/api/users/' + accounts['admin']['id'], json={'role': 'analista', 'active': True}).status_code == 409
    assert client.put('/api/users/' + accounts['admin']['id'], json={'role': 'administrador', 'active': False}).status_code == 409


def test_role_change_and_password_reset_revoke_sessions(client, accounts):
    with TestClient(app) as analyst:
        sign_in(analyst, accounts['analyst']['username'], accounts['analyst_password'])
        assert client.put('/api/users/' + accounts['analyst']['id'], json={'role': 'administrador', 'active': True}).status_code == 200
        assert analyst.get('/api/users').status_code == 401
        sign_in(analyst, accounts['analyst']['username'], accounts['analyst_password'])
        assert analyst.get('/api/users').status_code == 200
        new_password = secrets.token_urlsafe(24)
        assert client.put('/api/users/' + accounts['analyst']['id'], json={'role': 'analista', 'active': True, 'password': new_password}).status_code == 200
        assert analyst.get('/api/overview').status_code == 401
        assert attempt(analyst, accounts['analyst']['username'], accounts['analyst_password']).status_code == 401
        sign_in(analyst, accounts['analyst']['username'], new_password)
        assert analyst.get('/api/overview').status_code == 200


def test_absolute_idle_expiry_and_persistent_rate_limits(anonymous_client, accounts, monkeypatch):
    sign_in(anonymous_client, accounts['admin']['username'], accounts['admin_password'])
    with connection() as db:
        db.execute('UPDATE sessions SET expires_at=?', (auth.clock() - 1,))
    assert anonymous_client.get('/api/overview').status_code == 401
    sign_in(anonymous_client, accounts['admin']['username'], accounts['admin_password'])
    with connection() as db:
        db.execute('UPDATE sessions SET last_seen_at=?', (auth.clock() - auth.idle_lifetime() - 1,))
    assert anonymous_client.get('/api/overview').status_code == 401
    for _ in range(5):
        assert attempt(anonymous_client, accounts['analyst']['username'], secrets.token_urlsafe(24)).status_code == 401
    limited = attempt(anonymous_client, accounts['analyst']['username'], accounts['analyst_password'])
    assert limited.status_code == 429 and int(limited.headers['Retry-After']) > 0
    initialize()  # Restart/schema initialization must not clear throttles.
    assert attempt(anonymous_client, accounts['analyst']['username'], accounts['analyst_password']).status_code == 429
    later = auth.clock() + 901
    monkeypatch.setattr(auth, 'clock', lambda: later)
    sign_in(anonymous_client, accounts['analyst']['username'], accounts['analyst_password'])


def test_secure_cookie_under_https_configuration(anonymous_client, accounts, monkeypatch):
    monkeypatch.setenv('CENTINELA_COOKIE_SECURE', '1')
    # Read Set-Cookie rather than relying on browsers sending Secure over plain HTTP.
    with TestClient(app, base_url='https://testserver') as https:
        result = sign_in(https, accounts['admin']['username'], accounts['admin_password'])
        assert 'Secure' in result.headers['set-cookie'] and 'HttpOnly' in result.headers['set-cookie']
        assert https.get('/api/overview').status_code == 200


def test_password_change_revokes_session(client, accounts):
    new_password = secrets.token_urlsafe(24)
    result = client.post('/api/auth/password', json={'current_password': accounts['admin_password'], 'new_password': new_password})
    assert result.status_code == 200
    assert client.get('/api/overview').status_code == 401
    sign_in(client, accounts['admin']['username'], new_password)
    assert client.get('/api/overview').status_code == 200
