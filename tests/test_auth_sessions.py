import hashlib
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from src import auth
from src import auth_schema as s
from src.api.auth import router


@pytest.fixture
def auth_client(database, monkeypatch):
    monkeypatch.delenv('I9_MACHINE_KEY_ENABLED', raising=False)
    monkeypatch.delenv('I9_TRUSTED_ORIGINS', raising=False)
    application = FastAPI()
    application.include_router(router)

    @application.post('/private')
    def private(user=Depends(auth.require_admin)):
        return {'username': user['username']}

    with TestClient(application) as client:
        yield client


def sign_in(client):
    return client.post('/api/v3/auth/login', json={'username': 'admin.test', 'password': 'uma-senha-forte-2026'})


def test_login_cookie_csrf_and_logout(auth_client, database):
    auth.create_admin('Admin.Test', 'uma-senha-forte-2026')
    assert auth_client.get('/api/v3/auth/session').json()['authenticated'] is False
    assert auth_client.post('/private').status_code == 401
    response = sign_in(auth_client)
    assert response.status_code == 200
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert response.headers['cache-control'] == 'no-store'
    csrf = response.json()['csrf_token']
    assert auth_client.get('/api/v3/auth/session').json()['username'] == 'admin.test'
    assert auth_client.post('/private').status_code == 403
    assert auth_client.post('/private', headers={'X-CSRF-Token': 'invalid'}).status_code == 403
    assert auth_client.post('/private', headers={'X-CSRF-Token': csrf}).status_code == 200
    raw_token = auth_client.cookies[auth.COOKIE_NAME]
    with database.connect() as connection:
        stored = connection.execute(select(s.sessions)).mappings().one()
        assert stored['token_hash'] == hashlib.sha256(raw_token.encode()).hexdigest()
        assert raw_token not in str(stored)
    assert auth_client.post('/api/v3/auth/logout', headers={'X-CSRF-Token': csrf}).status_code == 204
    auth_client.cookies.set(auth.COOKIE_NAME, raw_token)
    assert auth_client.post('/private', headers={'X-CSRF-Token': csrf}).status_code == 401


def test_cross_site_login_and_csrf_are_rejected(auth_client):
    auth.create_admin('admin.test', 'uma-senha-forte-2026')
    response = auth_client.post('/api/v3/auth/login', headers={'Origin': 'https://attacker.example'},
        json={'username': 'admin.test', 'password': 'uma-senha-forte-2026'})
    assert response.status_code == 403
    csrf = sign_in(auth_client).json()['csrf_token']
    assert auth_client.post('/private', headers={'X-CSRF-Token': csrf, 'Origin': 'https://attacker.example'}).status_code == 403
    assert auth_client.post('/private', headers={'X-CSRF-Token': csrf, 'Origin': 'http://testserver'}).status_code == 200


def test_failures_throttled_persistently_and_recover(auth_client, database):
    auth.create_admin('admin.test', 'uma-senha-forte-2026')
    for _ in range(8):
        response = auth_client.post('/api/v3/auth/login', json={'username': 'admin.test', 'password': 'wrong-password'})
        assert response.status_code == 401
    response = sign_in(auth_client)
    assert response.status_code == 429 and int(response.headers['retry-after']) > 0
    with database.begin() as connection:
        assert connection.execute(select(s.login_limits.c.attempts)).first() is not None
        connection.execute(update(s.login_limits).values(window_start=int(time.time()) - 901))
    assert sign_in(auth_client).status_code == 200


def test_reset_and_expiry_revoke_sessions(auth_client, database):
    user_id = auth.create_admin('admin.test', 'uma-senha-forte-2026')
    csrf = sign_in(auth_client).json()['csrf_token']
    with database.begin() as connection:
        connection.execute(update(s.sessions).values(expires_at=int(time.time()) - 1))
    assert auth_client.post('/private', headers={'X-CSRF-Token': csrf}).status_code == 401
    csrf = sign_in(auth_client).json()['csrf_token']
    assert auth.create_admin('admin.test', 'outra-senha-forte-2026', reset=True) == user_id
    assert auth_client.post('/private', headers={'X-CSRF-Token': csrf}).status_code == 401
    assert sign_in(auth_client).status_code == 401


def test_machine_key_disabled_by_default(auth_client, monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY', 'a-secret-key')
    assert auth_client.post('/private', headers={'X-Admin-Key': 'a-secret-key'}).status_code == 401
    monkeypatch.setenv('I9_MACHINE_KEY_ENABLED', 'true')
    assert auth_client.post('/private', headers={'X-Admin-Key': 'a-secret-key'}).status_code == 200


def test_password_storage_unique_username_and_policy(database):
    with pytest.raises(ValueError):
        auth.create_admin('test', 'short')
    auth.create_admin('Admin.Test', 'uma-senha-forte-2026')
    with pytest.raises(ValueError):
        auth.create_admin('admin.test', 'uma-outra-senha-forte')
    with database.connect() as connection:
        row = connection.execute(select(s.users)).mappings().one()
        assert 'uma-senha-forte' not in row['password_hash']
        assert auth.verify_password('uma-senha-forte-2026', row['password_hash'])
        assert not auth.verify_password('wrong', row['password_hash'])
