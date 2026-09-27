from time import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.core.auth import Authenticator, Principal, current_user
from backend.app.core.config import Settings
from backend.app.main import app


@pytest.fixture
def auth(monkeypatch):
    instance = Authenticator(Settings(_env_file=None, watermark_secret="x" * 32,
        supabase_url="https://example.supabase.co", supabase_publishable_key="public"))
    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(instance.keys, "get_signing_key_from_jwt", lambda _: SimpleNamespace(key=private.public_key()))
    return instance, private


def token(auth, **changes):
    claims = dict(sub=str(uuid4()), iss=auth[0].issuer, aud="authenticated",
                  iat=int(time()), exp=int(time()) + 120, role="authenticated")
    claims.update(changes)
    return jwt.encode(claims, auth[1], algorithm="ES256", headers={"kid": "test"})


def test_valid_signature(auth):
    identity = str(uuid4())
    assert str(auth[0].verify(token(auth, sub=identity))) == identity


@pytest.mark.parametrize("changes", [
    {"exp": 1}, {"iss": "https://attacker.test/auth/v1"}, {"aud": "anon"},
    {"sub": "invalid"}, {"role": "service_role"}, {"role": "admin"},
    {"is_anonymous": True}, {"iat": int(time()) + 3600},
    {"session_id": "not-a-uuid"},
])
def test_invalid_claims(auth, changes):
    with pytest.raises(HTTPException) as error:
        auth[0].verify(token(auth, **changes))
    assert error.value.status_code == 401


def test_forged_signature(auth):
    other = (auth[0], ec.generate_private_key(ec.SECP256R1()))
    with pytest.raises(HTTPException) as error:
        auth[0].verify(token(other))
    assert error.value.status_code == 401


@pytest.mark.parametrize("claim", ["exp", "iat", "iss", "aud", "sub", "role"])
def test_required_claims(auth, claim):
    claims = jwt.decode(token(auth), options={"verify_signature": False})
    del claims[claim]
    signed = jwt.encode(claims, auth[1], algorithm="ES256", headers={"kid": "test"})
    with pytest.raises(HTTPException):
        auth[0].verify(signed)


def test_unsigned_and_symmetric_tokens_rejected(auth):
    for algorithm, key in [("none", None), ("HS256", "x" * 32)]:
        with pytest.raises(HTTPException):
            auth[0].verify(jwt.encode({"sub": str(uuid4())}, key, algorithm=algorithm))


def test_role_from_database_and_user_scoped_request(auth, monkeypatch):
    identity = str(uuid4())
    signed = token(auth, sub=identity, user_metadata={"role": "admin"})
    def get(url, **kwargs):
        assert kwargs["headers"]["Authorization"] == f"Bearer {signed}"
        assert kwargs["params"]["id"] == f"eq.{identity}"
        return httpx.Response(200, json=[{"id": identity, "role": "user"}], request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", get)
    assert auth[0].authenticate(signed).role == "user"


def test_session_id_comes_from_verified_claims(auth, monkeypatch):
    identity, session = uuid4(), uuid4()
    signed = token(auth, sub=str(identity), session_id=str(session))
    monkeypatch.setattr(httpx, "get", lambda url, **kw: httpx.Response(200,
        json=[{"id": str(identity), "role": "user"}], request=httpx.Request("GET", url)))
    assert auth[0].authenticate(signed).session_id == session


@pytest.mark.parametrize("rows", [[], [{"id": str(uuid4()), "role": "admin"}]])
def test_missing_or_wrong_profile_denied(auth, monkeypatch, rows):
    monkeypatch.setattr(httpx, "get", lambda url, **kw: httpx.Response(200, json=rows, request=httpx.Request("GET", url)))
    with pytest.raises(HTTPException) as error:
        auth[0].authenticate(token(auth))
    assert error.value.status_code == 403


def test_missing_authentication_denied():
    with TestClient(app) as client:
        for path in ("/api/v1/auth/me", "/api/v1/auth/admin-check"):
            assert client.get(path).status_code == 401
        for action in ("embed", "extract"):
            assert client.post(f"/api/v1/watermarks/docx/{action}").status_code == 401


def test_ordinary_user_cannot_access_admin_routes():
    app.dependency_overrides[current_user] = lambda: Principal(uuid4(), "user", "test")
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/auth/me").status_code == 200
            assert client.get("/api/v1/auth/admin-check").status_code == 403
            assert client.post("/api/v1/watermarks/docx/extract").status_code == 403
    finally:
        app.dependency_overrides.clear()
