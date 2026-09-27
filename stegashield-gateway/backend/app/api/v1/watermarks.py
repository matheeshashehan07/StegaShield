"""Retired proof-of-concept endpoints; no unaudited attribution path remains."""
from fastapi import APIRouter, Depends, HTTPException
from backend.app.core.auth import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.post("/docx/embed", deprecated=True)
@router.post("/docx/extract", deprecated=True)
def retired():
    raise HTTPException(410, "Use /documents/{id}/download and /forensics/docx.")
