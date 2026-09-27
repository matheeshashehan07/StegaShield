"""Verify Supabase access tokens and resolve roles using the caller's RLS context."""

from dataclasses import dataclass, field
from functools import lru_cache
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    id: UUID
    role: str
    token: str = field(repr=False)
    session_id: UUID | None = None


def unauthorized() -> HTTPException:
    return HTTPException(401, "Invalid or missing access token.", headers={"WWW-Authenticate": "Bearer"})


class Authenticator:
    def __init__(self, settings: Settings):
        self.url = settings.supabase_url.rstrip("/")
        self.issuer = settings.supabase_jwt_issuer or self.url + "/auth/v1"
        self.api_key = settings.supabase_publishable_key
        if not self.url.startswith("https://") or self.issuer != self.url + "/auth/v1" or not self.api_key:
            raise HTTPException(503, "Supabase authentication configuration is incomplete.")
        self.keys = jwt.PyJWKClient(self.issuer + "/.well-known/jwks.json", timeout=5, lifespan=60)

    def verify_claims(self, token: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in ("ES256", "RS256") or not isinstance(header.get("kid"), str):
                raise unauthorized()
            key = self.keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token, key.key, algorithms=["ES256", "RS256"],
                issuer=self.issuer, audience="authenticated",
                options={"require": ["exp", "iat", "iss", "aud", "sub", "role"]},
            )
            if claims["role"] != "authenticated" or claims.get("is_anonymous", False):
                raise unauthorized()
            UUID(claims["sub"])
            if claims.get("session_id") is not None:
                UUID(claims["session_id"])
            return claims
        except jwt.PyJWKClientConnectionError:
            raise HTTPException(503, "Authentication service unavailable.") from None
        except (jwt.PyJWTError, ValueError, TypeError):
            raise unauthorized() from None

    def verify(self, token: str) -> UUID:
        return UUID(self.verify_claims(token)["sub"])

    def authenticate(self, token: str) -> Principal:
        claims = self.verify_claims(token)
        user_id = UUID(claims["sub"])
        try:
            response = httpx.get(
                self.url + "/rest/v1/profiles",
                params={"id": f"eq.{user_id}", "select": "id,role"},
                headers={"apikey": self.api_key, "Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if response.status_code in (401, 403):
                raise unauthorized()
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or len(rows) != 1:
                raise HTTPException(403, "An application profile is required.")
            row = rows[0]
            if row.get("id") != str(user_id) or row.get("role") not in ("user", "admin"):
                raise HTTPException(403, "Invalid application profile.")
            session_id = UUID(claims["session_id"]) if claims.get("session_id") else None
            return Principal(user_id, row["role"], token, session_id)
        except (httpx.HTTPError, ValueError, AttributeError):
            raise HTTPException(503, "Profile service unavailable.") from None


@lru_cache
def get_authenticator() -> Authenticator:
    return Authenticator(get_settings())


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    return get_authenticator().authenticate(credentials.credentials)


def require_admin(user: Principal = Depends(current_user)) -> Principal:
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user
