from io import BytesIO
from uuid import uuid4

import pytest
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from backend.app.core.errors import InvalidDocumentError
from backend.app.watermarking.codec import SignedWatermarkCodec
from backend.app.watermarking.pdf_adapter import PdfWatermarkAdapter


def make_pdf(pages=1, image=False):
    writer = PdfWriter()
    for index in range(pages):
        page = writer.add_blank_page(300, 400)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        resources = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        page[NameObject('/Resources')] = resources
        content = f'0.2 0.5 0.3 rg 20 20 120 40 re f\n0 g BT /F1 16 Tf 30 330 Td (Confidential page {index + 1}) Tj ET\n'.encode()
        if image:
            picture = DecodedStreamObject()
            picture.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'), NameObject('/Width'): NumberObject(2), NameObject('/Height'): NumberObject(2), NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
            picture.set_data(bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0]))
            resources[NameObject('/XObject')] = DictionaryObject({NameObject('/Im1'): writer._add_object(picture)})
            content += b'q 80 0 0 80 100 100 cm /Im1 Do Q\n'
        stream = DecodedStreamObject(); stream.set_data(content)
        page.replace_contents(stream)
        if index % 2:
            page.rotate(90)
            page.cropbox.upper_right = (280, 380)
    output = BytesIO(); writer.write(output)
    return output.getvalue()


@pytest.fixture
def adapter():
    return PdfWatermarkAdapter(SignedWatermarkCodec(b'a-secure-test-secret-with-at-least-32-bytes'))


@pytest.mark.parametrize('pages,image', [(1, False), (3, False), (7, False), (2, True)])
def test_pdf_round_trip_and_pixel_identical_rendering(adapter, pages, image):
    original = make_pdf(pages, image)
    unchanged = bytes(original)
    token = uuid4()
    protected = adapter.embed(original, token)
    recovered = adapter.extract(protected)
    assert recovered.token == token
    assert recovered.valid_copies == min(5, pages)
    assert original == unchanged
    before, after = PdfReader(BytesIO(original)), PdfReader(BytesIO(protected))
    assert len(before.pages) == len(after.pages)
    assert [p.extract_text() for p in before.pages] == [p.extract_text() for p in after.pages]
    # Independent renderer, 144 DPI, full bitmap comparison including images/rotation.
    with pdfium.PdfDocument(original) as left, pdfium.PdfDocument(protected) as right:
        for index in range(pages):
            p1, p2 = left[index], right[index]
            b1, b2 = p1.render(scale=2), p2.render(scale=2)
            assert (b1.width, b1.height) == (b2.width, b2.height)
            assert bytes(b1.buffer) == bytes(b2.buffer)
            b1.close(); b2.close(); p1.close(); p2.close()


def test_plain_pdf_is_inconclusive(adapter):
    assert adapter.extract(make_pdf()) is None


def test_wrong_key_and_modified_frame_are_inconclusive(adapter):
    protected = adapter.embed(make_pdf(), uuid4())
    other = PdfWatermarkAdapter(SignedWatermarkCodec(b'z' * 32))
    assert other.extract(protected) is None
    # Change a body symbol while preserving delimiters and PDF structure.
    marker = b'/Payload <'
    position = protected.index(marker) + len(marker) + 4 + len(adapter.codec.START) * 4 + 8 * 4
    tampered = protected[:position] + (b'200c' if protected[position:position+4] == b'200b' else b'200b') + protected[position+4:]
    assert adapter.extract(tampered) is None


def test_conflicting_pdf_tokens_are_inconclusive(adapter):
    writer = PdfWriter()
    for _ in range(2):
        protected = adapter.embed(make_pdf(), uuid4())
        writer.add_page(PdfReader(BytesIO(protected)).pages[0])
    output = BytesIO(); writer.write(output)
    assert adapter.extract(output.getvalue()) is None


def test_watermarked_original_is_rejected(adapter):
    protected = adapter.embed(make_pdf(), uuid4())
    assert adapter.contains_watermark_frame(protected)
    with pytest.raises(InvalidDocumentError):
        adapter.embed(protected, uuid4())


@pytest.mark.parametrize('data', [b'', b'not a PDF', b'%PDF-1.7\ncorrupt\n%%EOF'])
def test_corrupt_pdf_rejected(adapter, data):
    with pytest.raises(InvalidDocumentError):
        adapter.extract(data)


def test_truncated_pdf_rejected(adapter):
    with pytest.raises(InvalidDocumentError):
        adapter.embed(make_pdf()[:-20], uuid4())


def test_encrypted_pdf_rejected(adapter):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    writer.encrypt('password')
    output = BytesIO(); writer.write(output)
    with pytest.raises(InvalidDocumentError):
        adapter.extract(output.getvalue())


@pytest.mark.parametrize('key', ['/AcroForm', '/OpenAction', '/AA', '/ByteRange', '/EmbeddedFiles', '/JS'])
def test_active_or_signed_pdf_rejected(adapter, key):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    writer.root_object[NameObject(key)] = DictionaryObject()
    output = BytesIO(); writer.write(output)
    with pytest.raises(InvalidDocumentError):
        adapter.embed(output.getvalue(), uuid4())


def test_page_and_expansion_limits(adapter, monkeypatch):
    # Limits are class-level for all workers.
    monkeypatch.setattr(PdfWatermarkAdapter, 'MAX_PAGES', 1)
    with pytest.raises(InvalidDocumentError):
        adapter.extract(make_pdf(2))
    monkeypatch.setattr(PdfWatermarkAdapter, 'MAX_CONTENT_BYTES', 10)
    with pytest.raises(InvalidDocumentError):
        adapter.extract(make_pdf())


def test_unique_pdf_download_tokens(adapter):
    original = make_pdf()
    tokens = [uuid4() for _ in range(10)]
    outputs = [adapter.embed(original, token) for token in tokens]
    assert len(set(outputs)) == 10
    assert [adapter.extract(data).token for data in outputs] == tokens


@pytest.mark.parametrize('action', sorted(PdfWatermarkAdapter.FORBIDDEN_ACTIONS))
def test_external_or_active_actions_rejected(adapter, action):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    writer.pages[0][NameObject('/A')] = DictionaryObject({NameObject('/S'): NameObject(action)})
    output = BytesIO()
    writer.write(output)
    with pytest.raises(InvalidDocumentError):
        adapter.embed(output.getvalue(), uuid4())


@pytest.mark.parametrize('marker', [b'/StegaShield DP', b'/StegaShield << >> DP', b'/StegaShield /Unknown DP'])
def test_malformed_existing_marker_rejected(adapter, marker):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    stream = DecodedStreamObject()
    stream.set_data(writer.pages[0].get_contents().get_data() + b'\n' + marker + b'\n')
    writer.pages[0].replace_contents(stream)
    output = BytesIO()
    writer.write(output)
    assert adapter.contains_watermark_frame(output.getvalue())
    assert adapter.extract(output.getvalue()) is None
    with pytest.raises(InvalidDocumentError):
        adapter.embed(output.getvalue(), uuid4())


def test_input_size_and_object_limits(adapter, monkeypatch):
    document = make_pdf()
    monkeypatch.setattr(PdfWatermarkAdapter, 'MAX_BYTES', len(document) - 1)
    with pytest.raises(InvalidDocumentError):
        adapter.extract(document)
    monkeypatch.setattr(PdfWatermarkAdapter, 'MAX_BYTES', len(document) + 10000)
    monkeypatch.setattr(PdfWatermarkAdapter, 'MAX_OBJECTS', 1)
    with pytest.raises(InvalidDocumentError):
        adapter.extract(document)


def test_output_size_limit(adapter, monkeypatch):
    document = make_pdf()
    monkeypatch.setattr(PdfWatermarkAdapter, 'MAX_BYTES', len(document) + 1)
    with pytest.raises(InvalidDocumentError):
        adapter.embed(document, uuid4())


def test_blank_page_without_content_stream(adapter):
    writer = PdfWriter()
    writer.add_blank_page(300, 400)
    output = BytesIO()
    writer.write(output)
    token = uuid4()
    assert adapter.extract(adapter.embed(output.getvalue(), token)).token == token
