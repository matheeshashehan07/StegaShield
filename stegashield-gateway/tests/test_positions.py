from uuid import uuid4
import pytest
from tests.test_workflow import workflow, admin

@pytest.mark.parametrize('path,method,body', [
    ('/admin/positions','get',None), ('/admin/positions','post',{'name':'Manager'}),
    ('/admin/position-memberships','get',None),
    ('/admin/users/{id}/position','post',{'position_id':str(uuid4())}),
    ('/admin/users/{id}/position','delete',None),
    ('/documents/{id}/position-permissions','post',{'position_id':str(uuid4())}),
    ('/documents/{id}/position-permissions','get',None),
    ('/documents/{id}/position-permissions/'+str(uuid4()),'delete',None)])
def test_position_routes_admin_only(workflow,path,method,body):
    client,gateway,_=workflow
    response=getattr(client,method)('/api/v1'+path.replace('{id}',str(gateway.id)), **({'json':body} if body else {}))
    assert response.status_code==403
    assert not gateway.writes

def test_grant_uses_admin_identity(workflow):
    client,gateway,_=workflow
    identity=admin(); position=str(uuid4())
    path=f'/api/v1/documents/{gateway.id}/position-permissions'
    assert client.post(path,json={'position_id':position,'granted_by':str(uuid4())}).status_code==422
    assert client.post(path,json={'position_id':position}).status_code==201
    assert gateway.writes[-1][2]['json']['granted_by']==str(identity.id)

def test_position_name_validation_and_membership_upsert(workflow):
    client,gateway,_=workflow
    admin()
    assert client.post('/api/v1/admin/positions',json={'name':'   '}).status_code==422
    assert client.post('/api/v1/admin/positions',json={'name':' Manager '}).status_code==201
    assert gateway.writes[-1][2]['json']=={'name':'Manager'}
    assert client.post(f'/api/v1/admin/users/{uuid4()}/position',json={'position_id':str(uuid4())}).status_code==200
    assert gateway.writes[-1][2]['prefer']=='resolution=merge-duplicates'
