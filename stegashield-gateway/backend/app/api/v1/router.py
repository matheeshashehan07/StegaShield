from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from backend.app.core.config import get_settings
import jwt
from backend.app.core.auth import Principal, current_user, require_admin

from backend.app.api.v1.watermarks import router as watermark_router
from backend.app.api.v1.documents import router as document_router
from backend.app.services.gateway import Gateway, get_gateway

api_router = APIRouter()
from backend.app.api.v1.profile_edit import router as profile_edit_router
api_router.include_router(profile_edit_router, tags=["Profile"])
from backend.app.api.v1.positions import router as position_router
api_router.include_router(position_router, tags=["Position access"])
api_router.include_router(watermark_router, prefix="/watermarks", tags=["Watermarks"])
api_router.include_router(document_router, tags=["Documents and forensics"])


@api_router.get("/auth/config", tags=["Authentication"])
def public_config():
    settings = get_settings()
    key = settings.supabase_publishable_key
    allowed = key.startswith("sb_publishable_")
    if not allowed:
        try:
            # Classify a configured legacy public key, not a user authentication token.
            allowed = jwt.decode(key, options={"verify_signature": False}).get("role") == "anon"
        except jwt.PyJWTError:
            pass
    if not allowed or not settings.supabase_url.startswith("https://"):
        raise HTTPException(503, "Public Supabase configuration is incomplete.")
    return JSONResponse({"url": settings.supabase_url.rstrip("/"), "publishableKey": key,
                         "supportedFormats": ["docx", "pdf"] if settings.pdf_enabled else ["docx"]},
                        headers={"Cache-Control": "no-store"})


@api_router.get("/auth/me", tags=["Authentication"])
def me(user: Principal = Depends(current_user)) -> dict[str, str]:
    return {"id": str(user.id), "role": user.role}


@api_router.get("/auth/admin-check", tags=["Authentication"])
def admin_check(user: Principal = Depends(require_admin)) -> dict[str, str]:
    return {"id": str(user.id), "role": user.role}


@api_router.get("/auth/profile", tags=["Authentication"])
def profile(user: Principal = Depends(current_user), gateway: Gateway = Depends(get_gateway)):
    rows = gateway.rows("profiles", user, id=f"eq.{user.id}",
                        select="id,display_name,created_at", limit="1")
    if len(rows) != 1 or rows[0].get("id") != str(user.id):
        raise HTTPException(503, "Your profile is temporarily unavailable.")
    row = rows[0]
    return JSONResponse({"id": str(user.id), "role": user.role,
                         "display_name": row.get("display_name"), "created_at": row.get("created_at")},
                        headers={"Cache-Control": "no-store"})
