from hashlib import sha256
from ipaddress import ip_address
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from backend.app.core.auth import Principal, current_user, require_admin
from backend.app.core.config import get_settings
from backend.app.core.errors import InvalidDocumentError
from backend.app.services.document_service import DocumentWatermarkService
from backend.app.services.gateway import Gateway, MIMES, get_gateway

router = APIRouter()


@router.get("/admin/users")
def list_users(user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    return gateway.rows("profiles", user, select="id,display_name,role", order="created_at.desc", limit="100")


@router.get("/admin/forensic-events")
def list_forensic_events(user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    return gateway.rows("forensic_events", user,
        select="id,attempt_id,performed_by,outcome,reason,completed,attempted_at,matched_download_id",
        order="attempted_at.desc", limit="50")


@router.get("/documents/{document_id}/permissions")
def list_permissions(document_id: UUID, user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    gateway.document(document_id, user)
    return gateway.rows("document_permissions", user, document_id=f"eq.{document_id}",
                        select="user_id,granted_at,expires_at")


def enabled_format(format):
    if format not in MIMES or (format == "pdf" and not get_settings().pdf_enabled):
        raise HTTPException(415, "Document format is not enabled.")
    return format


def read_docx(file, format="docx"):
    try:
        enabled_format(format)
        if PurePosixPath((file.filename or "").replace("\\", "/")).suffix.lower() != f".{format}":
            raise HTTPException(415, f"A .{format} file is required.")
        data = file.file.read(get_settings().max_upload_size_bytes + 1)
        if not data or len(data) > get_settings().max_upload_size_bytes:
            raise HTTPException(413, "File is empty or exceeds the upload limit.")
        return data
    finally:
        file.file.close()


@router.get("/documents")
def list_documents(user: Principal = Depends(current_user), gateway: Gateway = Depends(get_gateway)):
    return gateway.rows("documents", user, archived_at="is.null", format="in.(docx,pdf)" if get_settings().pdf_enabled else "eq.docx",
        select="id,title,original_filename,format,size_bytes,created_at", order="created_at.desc", limit="100")


@router.post("/documents", status_code=201)
def upload_document(file: UploadFile = File(...), title: str = Form(..., min_length=1, max_length=255),
                    user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    format = PurePosixPath((file.filename or "").replace("\\", "/")).suffix.lower().lstrip(".")
    data = read_docx(file, format)
    service = DocumentWatermarkService.from_settings()
    if service.adapter(format).contains_watermark_frame(data):
        raise HTTPException(422, "Upload an original without an existing watermark.")
    service.embed(data, format)
    document_id = uuid4()
    path = f"{document_id}/original.{format}"
    gateway.store_original(path, data)
    gateway.request("POST", "/rest/v1/documents", user=user, json={
        "id": str(document_id), "title": title, "original_filename": f"original.{format}",
        "storage_path": path, "format": format, "mime_type": MIMES[format],
        "size_bytes": len(data), "sha256": sha256(data).hexdigest(), "uploaded_by": str(user.id)})
    return {"id": str(document_id), "title": title}


class PermissionGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID


@router.post("/documents/{document_id}/permissions", status_code=201)
def grant_permission(document_id: UUID, grant: PermissionGrant,
                     user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    gateway.document(document_id, user)
    gateway.request("POST", "/rest/v1/document_permissions", user=user, json={
        "document_id": str(document_id), "user_id": str(grant.user_id), "granted_by": str(user.id)})
    return {"document_id": str(document_id), "user_id": str(grant.user_id)}


@router.delete("/documents/{document_id}/permissions/{user_id}", status_code=204)
def revoke_permission(document_id: UUID, user_id: UUID,
                      admin: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    gateway.request("DELETE", "/rest/v1/document_permissions", user=admin,
        params={"document_id": f"eq.{document_id}", "user_id": f"eq.{user_id}"})
    return Response(status_code=204)


@router.post("/documents/{document_id}/download")
def download_document(document_id: UUID, request: Request,
                      user: Principal = Depends(current_user), gateway: Gateway = Depends(get_gateway)):
    document = gateway.document(document_id, user)
    format = enabled_format(document["format"])
    original = gateway.original(document)
    if len(original) != document["size_bytes"] or sha256(original).hexdigest() != document["sha256"]:
        raise HTTPException(503, "Original document integrity check failed.")
    service = DocumentWatermarkService.from_settings()
    if service.adapter(format).contains_watermark_frame(original):
        raise HTTPException(422, "Stored original already contains a watermark.")
    protected = service.embed(original, format)
    try:
        address = str(ip_address(request.client.host)) if request.client else None
    except ValueError:
        address = None
    event_id = gateway.record_download(user, document_id, protected.token,
        sha256(protected.document).hexdigest(), address, request.headers.get("user-agent", "")[:512])
    try:
        UUID(str(event_id))
    except ValueError:
        raise HTTPException(503, "Download record was not acknowledged.") from None
    return Response(protected.document, media_type=MIMES[format], headers={
        "Content-Disposition": f'attachment; filename="{document_id}-protected.{format}"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/forensics/{format}")
def forensic_lookup(format: str, file: UploadFile = File(...), user: Principal = Depends(require_admin),
                    gateway: Gateway = Depends(get_gateway)):
    record = {"performed_by": str(user.id), "outcome": "inconclusive", "valid_copies": 0,
              "reason": "no_unique_valid_token", "attempt_id": str(uuid4()), "completed": True}
    # Write an append-only start record before parsing. A crash or lookup outage
    # leaves an observable unfinished attempt without storing the suspect file.
    gateway.audit({**record, "reason": "attempt_started", "completed": False})
    try:
        data = read_docx(file, format)
        recovered = DocumentWatermarkService.from_settings().adapter(format).extract(data)
        match = None
        if recovered:
            record.update(watermark_token=str(recovered.token), valid_copies=recovered.valid_copies)
            match = gateway.lookup(recovered.token, user)
            record["reason"] = "token_not_registered"
        if match and sha256(data).hexdigest() != match.get("protected_sha256"):
            match = None
            record["reason"] = "document_bytes_changed"
        if match:
            record.update(outcome="matched", matched_download_id=match["id"], reason="signed_token_registered")
        gateway.audit(record)
        if not match:
            return {"outcome": "inconclusive", "reason": record["reason"]}
        return {"outcome": "matched", "download": {k: match[k] for k in
            ("id", "user_id", "document_id", "downloaded_at")},
            "exact_copy": True,
            "message": "Signed token resolves to this download record; this alone does not prove who leaked the file."}
    except (InvalidDocumentError, HTTPException) as error:
        if isinstance(error, InvalidDocumentError) or (isinstance(error, HTTPException) and error.status_code in (413, 415)):
            record["reason"] = "invalid_document"
            gateway.audit(record)
        raise
