import base64
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.auth import Principal, current_user
from backend.app.services.gateway import get_gateway
from backend.app.api.v1.profile_edit import normalise_photo


def picture(format='PNG', size=(300, 200)):
    output = BytesIO()
    image = Image.new('RGB', size, 'red')
    image.save(output, format)
    return output.getvalue()


@pytest.fixture
def account():
    user = Principal(uuid4(), 'user', 'private-token')
    writes = []
    def request(method, path, **kwargs):
        assert method == 'POST' and path == '/rest/v1/rpc/update_profile_details'
        assert kwargs.get('user') is None
        writes.append(kwargs['json'])
        return True
    app.dependency_overrides[current_user] = lambda: user
    app.dependency_overrides[get_gateway] = lambda: SimpleNamespace(request=request, rows=lambda *a, **k: [])
    try:
        with TestClient(app) as client:
            yield client, user, writes
    finally:
        app.dependency_overrides.clear()


def test_name_only_updates_verified_user(account):
    client, user, writes = account
    response = client.post('/api/v1/auth/profile', data={'display_name': ' Alice '})
    assert response.status_code == 204
    assert writes == [{'p_user_id': str(user.id), 'p_display_name': 'Alice', 'p_change_photo': False, 'p_image_base64': None}]
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('field', ['role', 'user_id', 'email', 'position_id', 'avatar_url'])
def test_other_fields_rejected(account, field):
    client, _, writes = account
    assert client.post('/api/v1/auth/profile', data={'display_name': 'Alice', field: 'attacker'}).status_code == 422
    assert not writes


@pytest.mark.parametrize('name', ['', '   ', 'x' * 121])
def test_invalid_names_do_not_write(account, name):
    client, _, writes = account
    assert client.post('/api/v1/auth/profile', data={'display_name': name}).status_code == 422
    assert not writes


def test_photo_normalised_before_atomic_save(account):
    client, _, writes = account
    response = client.post('/api/v1/auth/profile', data={'display_name': 'Alice'}, files={'photo': ('untrusted.exe', picture(), 'text/plain')})
    assert response.status_code == 204
    image = Image.open(BytesIO(base64.b64decode(writes[0]['p_image_base64'])))
    assert image.format == 'JPEG' and max(image.size) == 256
    assert not image.getexif()
    assert writes[0]['p_change_photo'] is True


@pytest.mark.parametrize('data,status', [(b'<svg onload="alert(1)"></svg>', 422), (picture('GIF'), 415), (b'x' * (2 * 1024 * 1024 + 1), 413), (picture(size=(4097, 1)), 413)], ids=['svg', 'gif', 'size', 'dimensions'])
def test_unsafe_or_oversized_picture_rejected(account, data, status):
    client, _, writes = account
    assert client.post('/api/v1/auth/profile', data={'display_name': 'Alice'}, files={'photo': ('photo.png', data)}).status_code == status
    assert not writes


def test_remove_photo(account):
    client, _, writes = account
    assert client.post('/api/v1/auth/profile', data={'display_name': 'Alice', 'remove_photo': 'true'}).status_code == 204
    assert writes[0]['p_change_photo'] is True and writes[0]['p_image_base64'] is None


def test_replace_and_remove_cannot_be_combined(account):
    client, _, writes = account
    assert client.post('/api/v1/auth/profile', data={'display_name': 'Alice', 'remove_photo': 'true'}, files={'photo': ('a.png', picture())}).status_code == 422
    assert not writes


def test_photo_read_is_scoped_and_private(account):
    client, user, _ = account
    data = normalise_photo(picture())
    def rows(table, principal, **filters):
        assert table == 'profile_photos' and principal == user
        assert filters['user_id'] == f'eq.{user.id}'
        return [{'user_id': str(user.id), 'image_base64': base64.b64encode(data).decode()}]
    app.dependency_overrides[get_gateway] = lambda: SimpleNamespace(rows=rows)
    response = client.get(f'/api/v1/auth/profile/photo?user_id={uuid4()}')
    assert response.content == data
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_unacknowledged_save_fails(account):
    client, _, _ = account
    app.dependency_overrides[get_gateway] = lambda: SimpleNamespace(request=lambda *a, **k: None)
    assert client.post('/api/v1/auth/profile', data={'display_name': 'Alice'}).status_code == 503


def test_profile_edits_and_photos_require_auth(account):
    client, _, _ = account
    app.dependency_overrides.pop(current_user)
    assert client.post('/api/v1/auth/profile', data={'display_name': 'Alice'}).status_code == 401
    assert client.get('/api/v1/auth/profile/photo').status_code == 401
