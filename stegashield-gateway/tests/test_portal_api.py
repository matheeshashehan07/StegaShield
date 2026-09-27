from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.v1 import router
from backend.app.core.auth import Principal, current_user
from backend.app.services.gateway import get_gateway


@pytest.mark.parametrize('role', ['user', 'admin'])
def test_profile_is_self_scoped_and_allowlisted(role):
    identity = Principal(uuid4(), role, 'SECRET_TOKEN')
    def rows(table, user, **filters):
        assert table == 'profiles' and user == identity
        assert filters == {'id': f'eq.{identity.id}', 'select': 'id,display_name,created_at', 'limit': '1'}
        return [{'id': str(identity.id), 'display_name': 'Test member', 'created_at': '2026-09-01T00:00:00Z', 'secret': 'DO_NOT_EXPOSE'}]
    app.dependency_overrides[current_user] = lambda: identity
    app.dependency_overrides[get_gateway] = lambda: SimpleNamespace(rows=rows)
    try:
        with TestClient(app) as client:
            response = client.get(f'/api/v1/auth/profile?user_id={uuid4()}')
        assert response.status_code == 200
        assert response.json() == {'id': str(identity.id), 'role': role, 'display_name': 'Test member', 'created_at': '2026-09-01T00:00:00Z'}
        assert response.headers['cache-control'] == 'no-store'
        assert 'SECRET_TOKEN' not in response.text and 'DO_NOT_EXPOSE' not in response.text
    finally:
        app.dependency_overrides.clear()


def test_profile_requires_authentication():
    with TestClient(app) as client:
        assert client.get('/api/v1/auth/profile').status_code == 401


@pytest.mark.parametrize('rows', [[], [{'id': str(uuid4()), 'display_name': 'Other user'}]])
def test_profile_missing_or_wrong_identity_is_not_disclosed(rows):
    app.dependency_overrides[current_user] = lambda: Principal(uuid4(), 'user', 'test')
    app.dependency_overrides[get_gateway] = lambda: SimpleNamespace(rows=lambda *a, **k: rows)
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/auth/profile')
        assert response.status_code == 503
        assert 'Other user' not in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize('pdf_enabled', [False, True])
def test_public_configuration_is_explicit_allowlist(monkeypatch, pdf_enabled):
    monkeypatch.setattr(router, 'get_settings', lambda: SimpleNamespace(
        supabase_url='https://example.supabase.co', supabase_publishable_key='sb_publishable_test',
        supabase_secret_key='SERVER_SECRET', watermark_secret='WATERMARK_SECRET', pdf_enabled=pdf_enabled))
    with TestClient(app) as client:
        response = client.get('/api/v1/auth/config')
    assert response.status_code == 200
    assert response.json() == {'url': 'https://example.supabase.co', 'publishableKey': 'sb_publishable_test',
                               'supportedFormats': ['docx', 'pdf'] if pdf_enabled else ['docx']}
    assert response.headers['cache-control'] == 'no-store'
    assert 'SERVER_SECRET' not in response.text
    assert 'WATERMARK_SECRET' not in response.text


@pytest.mark.parametrize('key', ['sb_secret_accidentally_configured', '', jwt.encode({'role': 'service_role'}, 'x' * 32)])
def test_misconfigured_secret_is_not_published(monkeypatch, key):
    monkeypatch.setattr(router, 'get_settings', lambda: SimpleNamespace(
        supabase_url='https://example.supabase.co', supabase_publishable_key=key))
    with TestClient(app) as client:
        response = client.get('/api/v1/auth/config')
    assert response.status_code == 503
    if key:
        assert key not in response.text


@pytest.mark.parametrize('role,status', [(None, 401), ('user', 403), ('admin', 200)])
def test_portal_admin_reads_enforce_role(role, status):
    identity = Principal(uuid4(), role or 'user', 'test')
    calls = []
    def rows(table, user, **filters):
        assert user == identity
        calls.append((table, filters))
        return []
    app.dependency_overrides[get_gateway] = lambda: SimpleNamespace(rows=rows, document=lambda *args: {})
    if role:
        app.dependency_overrides[current_user] = lambda: identity
    try:
        with TestClient(app) as client:
            for path in ['/admin/users', '/admin/forensic-events', f'/documents/{uuid4()}/permissions']:
                assert client.get('/api/v1' + path).status_code == status
        assert len(calls) == (3 if role == 'admin' else 0)
        for _, query in calls:
            assert 'watermark_token' not in query['select']
    finally:
        app.dependency_overrides.clear()
