"""Health and retirement coverage; round trips now live in test_workflow.py."""
from uuid import uuid4

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.auth import Principal, current_user


def test_health_endpoint():
    with TestClient(app) as client:
        assert client.get('/health').json()['status'] == 'ok'


def test_untracked_watermark_routes_retired():
    app.dependency_overrides[current_user] = lambda: Principal(uuid4(), 'admin', 'test')
    try:
        with TestClient(app) as client:
            for action in ('embed', 'extract'):
                assert client.post('/api/v1/watermarks/docx/' + action).status_code == 410
    finally:
        app.dependency_overrides.clear()
