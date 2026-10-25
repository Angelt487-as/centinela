import secrets
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.auth import create_user


@pytest.fixture
def anonymous_client(tmp_path, monkeypatch):
    monkeypatch.setenv('CENTINELA_DATA_DIR', str(tmp_path / 'data'))
    with TestClient(app) as test_client:
        yield test_client


def sign_in(client, username, password):
    challenge = client.get('/api/auth/csrf').json()['csrf_token']
    response = client.post('/api/auth/login', json={'username': username, 'password': password},
                           headers={'X-CSRF-Token': challenge})
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    return response


@pytest.fixture
def accounts(anonymous_client):
    admin_password, analyst_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    admin = create_user('admin-pruebas', admin_password, 'administrador')
    analyst = create_user('analista-pruebas', analyst_password)
    return {'admin': admin, 'admin_password': admin_password, 'analyst': analyst, 'analyst_password': analyst_password}


@pytest.fixture
def client(anonymous_client, accounts):
    sign_in(anonymous_client, accounts['admin']['username'], accounts['admin_password'])
    return anonymous_client
