from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from backend.app.core.auth import Principal, require_admin
from backend.app.services.gateway import Gateway, get_gateway

router = APIRouter()

class PositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str

class PositionGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position_id: UUID

@router.get('/admin/positions')
def positions(user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    return gateway.rows('job_positions', user, select='id,name', order='name', limit='100')

@router.post('/admin/positions', status_code=201)
def create_position(body: PositionCreate, user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    name = body.name.strip()
    if not 1 <= len(name) <= 120:
        raise HTTPException(422, 'Position name must contain 1 to 120 characters.')
    gateway.request('POST', '/rest/v1/job_positions', user=user, json={'name': name})
    return {'name': name}

@router.get('/admin/position-memberships')
def memberships(user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    return gateway.rows('position_memberships', user, select='user_id,position_id', limit='1000')

@router.post('/admin/users/{user_id}/position')
def assign_position(user_id: UUID, body: PositionGrant, user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    gateway.request('POST', '/rest/v1/position_memberships', user=user, params={'on_conflict': 'user_id'},
                    json={'user_id': str(user_id), 'position_id': str(body.position_id)}, prefer='resolution=merge-duplicates')
    return {'user_id': str(user_id)}

@router.delete('/admin/users/{user_id}/position', status_code=204)
def remove_position(user_id: UUID, user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    gateway.request('DELETE', '/rest/v1/position_memberships', user=user, params={'user_id': f'eq.{user_id}'})
    return Response(status_code=204)

@router.get('/documents/{document_id}/position-permissions')
def permissions(document_id: UUID, user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    gateway.document(document_id, user)
    return gateway.rows('document_position_permissions', user, document_id=f'eq.{document_id}', select='position_id,granted_at')

@router.post('/documents/{document_id}/position-permissions', status_code=201)
def grant(document_id: UUID, body: PositionGrant, user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    gateway.document(document_id, user)
    gateway.request('POST', '/rest/v1/document_position_permissions', user=user,
                    json={'document_id': str(document_id), 'position_id': str(body.position_id), 'granted_by': str(user.id)})
    return {'position_id': str(body.position_id)}

@router.delete('/documents/{document_id}/position-permissions/{position_id}', status_code=204)
def revoke(document_id: UUID, position_id: UUID, user: Principal = Depends(require_admin), gateway: Gateway = Depends(get_gateway)):
    gateway.request('DELETE', '/rest/v1/document_position_permissions', user=user,
                    params={'document_id': f'eq.{document_id}', 'position_id': f'eq.{position_id}'})
    return Response(status_code=204)
