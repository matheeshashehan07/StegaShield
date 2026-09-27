from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json

import httpx
import pytest
from fastapi import HTTPException

from backend.app.core.auth import Principal
from backend.app.core.config import Settings
from backend.app.services.gateway import Gateway


def gateway(handler):
    return Gateway(Settings(_env_file=None, watermark_secret='x' * 32,
        supabase_url='https://example.supabase.co', supabase_publishable_key='publishable',
        supabase_secret_key='sb_secret_server'), httpx.MockTransport(handler))


@pytest.mark.parametrize('permission', [[], [{'expires_at': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}]])
def test_permission_explicitly_checked_with_callers_rls(permission):
    identity = Principal(uuid4(), 'user', 'user-token')
    document_id = uuid4()
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers['authorization'] == 'Bearer user-token'
        assert request.headers['apikey'] == 'publishable'
        if request.url.path.endswith('/has_position_access'):
            assert json.loads(request.content) == {'p_document_id': str(document_id)}
            return httpx.Response(200, json=False)
        if request.url.path.endswith('/documents'):
            assert request.url.params['archived_at'] == 'is.null'
            return httpx.Response(200, json=[{'id': str(document_id), 'format': 'docx'}])
        assert request.url.params['user_id'] == f'eq.{identity.id}'
        return httpx.Response(200, json=permission)
    with pytest.raises(HTTPException) as error:
        gateway(handler).document(document_id, identity)
    assert error.value.status_code == 404
    assert len(calls) == 3


def test_record_download_uses_server_only_rpc():
    user = Principal(uuid4(), 'user', 'user-token')
    doc, token, event = uuid4(), uuid4(), uuid4()
    def handler(request):
        assert request.url.path == '/rest/v1/rpc/record_download'
        assert request.headers['apikey'] == 'sb_secret_server'
        assert 'authorization' not in request.headers
        body = json.loads(request.content)
        assert body['p_user_id'] == str(user.id)
        assert body['p_token'] == str(token)
        assert body['p_document_id'] == str(doc)
        return httpx.Response(200, json=str(event))
    assert gateway(handler).record_download(user, doc, token, 'a' * 64, None, '') == str(event)


def test_position_access_fallback_uses_callers_jwt():
    identity = Principal(uuid4(), 'user', 'member-token')
    document_id = uuid4()
    def handler(request):
        assert request.headers['authorization'] == 'Bearer member-token'
        if request.url.path.endswith('/documents'):
            return httpx.Response(200, json=[{'id': str(document_id), 'format': 'docx'}])
        if request.url.path.endswith('/document_permissions'):
            return httpx.Response(200, json=[])
        assert request.url.path.endswith('/rpc/has_position_access')
        assert json.loads(request.content) == {'p_document_id': str(document_id)}
        return httpx.Response(200, json=True)
    assert gateway(handler).document(document_id, identity)['id'] == str(document_id)


@pytest.mark.parametrize('code,expected', [(401, 403), (403, 403), (500, 503)])
def test_upstream_errors_are_sanitized(code, expected):
    instance = gateway(lambda _: httpx.Response(code, text='SECRET database internals'))
    with pytest.raises(HTTPException) as error:
        instance.audit({})
    assert error.value.status_code == expected
    assert 'SECRET' not in error.value.detail


def test_lookup_uses_admin_jwt_not_service_key():
    def handler(request):
        assert request.headers['authorization'] == 'Bearer admin-token'
        assert request.headers['apikey'] == 'publishable'
        return httpx.Response(200, json=[])
    assert gateway(handler).lookup(uuid4(), Principal(uuid4(), 'admin', 'admin-token')) is None


def test_object_path_injection_rejected_before_network():
    calls = []
    instance = gateway(lambda request: calls.append(request))
    with pytest.raises(HTTPException):
        instance.original({'id': str(uuid4()), 'storage_path': '../../other-bucket/file'})
    assert calls == []


def test_original_stream_has_size_bound():
    document_id = uuid4()
    instance = gateway(lambda _: httpx.Response(200, content=b'x' * 2048))
    instance.settings.max_upload_size_bytes = 1024
    with pytest.raises(HTTPException) as error:
        instance.original({'id': str(document_id), 'storage_path': f'{document_id}/original.docx'})
    assert error.value.status_code == 503


def test_upload_does_not_overwrite_and_uses_server_key():
    def handler(request):
        assert request.headers['x-upsert'] == 'false'
        assert request.headers['apikey'] == 'sb_secret_server'
        assert 'authorization' not in request.headers
        assert request.content == b'original'
        return httpx.Response(200, json={})
    gateway(handler).store_original(f'{uuid4()}/original.docx', b'original')
