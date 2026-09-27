from hashlib import sha256
from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from backend.app.core.config import get_settings, Settings
from tests.test_workflow import workflow, admin
from tests.test_pdf_adapter import make_pdf


@pytest.fixture
def pdf_workflow(workflow, monkeypatch):
    monkeypatch.setattr(get_settings(), 'pdf_enabled', True)
    client, gateway, user = workflow
    gateway.data = make_pdf()
    gateway.metadata.update(format='pdf', size_bytes=len(gateway.data), sha256=sha256(gateway.data).hexdigest())
    return client, gateway, user


def download(client, gateway):
    return client.post(f'/api/v1/documents/{gateway.id}/download')


def examine(client, data):
    return client.post('/api/v1/forensics/pdf', files={'file': ('suspect.pdf', data)})


def test_pdf_default_disabled(pdf_workflow, monkeypatch):
    assert Settings(_env_file=None, watermark_secret='x' * 32).pdf_enabled is False
    monkeypatch.setattr(get_settings(), 'pdf_enabled', False)
    client, gateway, _ = pdf_workflow
    assert download(client, gateway).status_code == 415
    assert gateway.reads == 0
    admin()
    assert examine(client, gateway.data).status_code == 415
    assert client.post('/api/v1/documents', data={'title': 'PDF'}, files={'file': ('a.pdf', gateway.data)}).status_code == 415
    assert not gateway.uploads


def test_pdf_authenticated_roundtrip(pdf_workflow):
    client, gateway, user = pdf_workflow
    first, second = download(client, gateway), download(client, gateway)
    assert first.status_code == second.status_code == 200
    assert first.content != second.content
    assert len(gateway.events) == 2
    assert first.headers['content-type'] == 'application/pdf'
    assert first.headers['content-disposition'].endswith('-protected.pdf"')
    assert first.headers['cache-control'] == 'no-store'
    assert 'x-watermark-token' not in first.headers
    admin()
    result = examine(client, first.content)
    assert result.json()['outcome'] == 'matched'
    assert result.json()['download']['user_id'] == str(user.id)
    assert gateway.audits[-1]['completed'] is True


@pytest.mark.parametrize('failure', ['permission', 'record', 'integrity'])
def test_pdf_failures_never_return_bytes(pdf_workflow, failure):
    client, gateway, _ = pdf_workflow
    if failure == 'permission':
        gateway.allowed = False
    elif failure == 'record':
        gateway.fail_record = True
    else:
        gateway.data += b'changed'
    response = download(client, gateway)
    assert response.status_code == (404 if failure == 'permission' else 503)
    assert 'content-disposition' not in response.headers
    assert not response.content.startswith(b'%PDF')
    assert not gateway.events


def test_pdf_member_cannot_upload_or_investigate(pdf_workflow):
    client, gateway, _ = pdf_workflow
    assert examine(client, gateway.data).status_code == 403
    assert client.post('/api/v1/documents', data={'title': 'PDF'}, files={'file': ('a.pdf', gateway.data)}).status_code == 403
    assert not gateway.uploads and not gateway.audits


@pytest.mark.parametrize('kind', ['plain', 'unknown', 'changed'])
def test_pdf_inconclusive_does_not_disclose_identity(pdf_workflow, kind):
    client, gateway, _ = pdf_workflow
    data = download(client, gateway).content
    if kind == 'plain':
        data = gateway.data
    elif kind == 'unknown':
        gateway.events.clear()
    else:
        writer = PdfWriter(clone_from=PdfReader(BytesIO(data)))
        writer.add_metadata({'/Title': 'Changed'})
        output = BytesIO()
        writer.write(output)
        data = output.getvalue()
    admin()
    result = examine(client, data)
    assert result.json()['outcome'] == 'inconclusive'
    assert 'download' not in result.json()


def test_pdf_audit_failure_hides_match(pdf_workflow):
    client, gateway, _ = pdf_workflow
    data = download(client, gateway).content
    admin()
    gateway.fail_audit = True
    assert examine(client, data).status_code == 503


def test_pdf_upload_server_metadata_and_cross_format_rejection(pdf_workflow):
    client, gateway, _ = pdf_workflow
    admin()
    result = client.post('/api/v1/documents', data={'title': 'PDF'}, files={'file': ('../../a.pdf', gateway.data, 'text/plain')})
    assert result.status_code == 201
    row = gateway.writes[-1][2]['json']
    assert row['format'] == 'pdf' and row['mime_type'] == 'application/pdf'
    assert row['original_filename'] == 'original.pdf'
    assert gateway.uploads[-1][0] == f"{row['id']}/original.pdf"
    assert client.post('/api/v1/forensics/docx', files={'file': ('a.docx', gateway.data)}).status_code == 422
    assert gateway.audits[-1]['reason'] == 'invalid_document'


def test_pdf_protected_original_rejected(pdf_workflow):
    client, gateway, _ = pdf_workflow
    data = download(client, gateway).content
    admin()
    assert client.post('/api/v1/documents', data={'title': 'PDF'}, files={'file': ('a.pdf', data)}).status_code == 422
    assert not gateway.uploads
