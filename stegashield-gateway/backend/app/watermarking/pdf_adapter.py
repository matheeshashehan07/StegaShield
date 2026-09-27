"""Static PDF carrier: a non-rendering marked-content point on up to five pages.

Uses the same signed UUID codec as DOCX. This is page-content metadata, not
rendered text, encryption, a PDF digital signature, or print/screenshot protection.
"""
from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, IndirectObject

from backend.app.core.errors import InvalidDocumentError
from backend.app.watermarking.base import WatermarkAdapter
from backend.app.watermarking.codec import SignedWatermarkCodec


@dataclass(frozen=True)
class ExtractedPdfWatermark:
    token: UUID
    valid_copies: int


class PdfWatermarkAdapter(WatermarkAdapter):
    MAX_BYTES = 10 * 1024 * 1024
    MAX_PAGES = 100
    MAX_CONTENT_BYTES = 20 * 1024 * 1024
    MAX_OBJECTS = 20000
    TAG = '/StegaShield'
    FORBIDDEN = {'/AcroForm', '/OpenAction', '/AA', '/JavaScript', '/JS',
                 '/EmbeddedFiles', '/EF', '/RichMedia', '/XFA', '/ByteRange'}
    FORBIDDEN_ACTIONS = {'/JavaScript', '/Launch', '/GoToR', '/SubmitForm', '/ImportData', '/Rendition'}

    def __init__(self, codec: SignedWatermarkCodec):
        self.codec = codec

    @classmethod
    def _read(cls, data: bytes):
        if not data or len(data) > cls.MAX_BYTES or not data.startswith(b'%PDF-') or not data.rstrip().endswith(b'%%EOF'):
            raise InvalidDocumentError('A complete PDF up to 10 MB is required.')
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise InvalidDocumentError('Password-protected PDFs are not supported.')
        if not 1 <= len(reader.pages) <= cls.MAX_PAGES:
            raise InvalidDocumentError('PDFs must contain between 1 and 100 pages.')
        seen = set()
        stack = [(reader.trailer, 0)]
        count = 0
        while stack:
            obj, depth = stack.pop()
            count += 1
            if count > cls.MAX_OBJECTS or depth > 60:
                raise InvalidDocumentError('The PDF object graph exceeds safe limits.')
            if isinstance(obj, IndirectObject):
                key = (obj.idnum, obj.generation)
                if key in seen:
                    continue
                seen.add(key)
                obj = obj.get_object()
            if isinstance(obj, DictionaryObject):
                if cls.FORBIDDEN.intersection(obj.keys()) or obj.get('/S') in cls.FORBIDDEN_ACTIONS:
                    raise InvalidDocumentError('Interactive, signed, attached-file, or script-bearing PDFs are not supported.')
                stack.extend((value, depth + 1) for value in obj.values())
            elif isinstance(obj, ArrayObject):
                stack.extend((value, depth + 1) for value in obj)
        total = 0
        for page in reader.pages:
            content = page.get_contents()
            if content is not None:
                total += len(content.get_data())
                if total > cls.MAX_CONTENT_BYTES:
                    raise InvalidDocumentError('Expanded PDF page content exceeds safe limits.')
                # Force strict content parsing, including during initial upload.
                if len(content.operations) > 200000:
                    raise InvalidDocumentError('PDF page complexity exceeds safe limits.')
        return reader

    def _frames(self, reader):
        for page in reader.pages:
            content = page.get_contents()
            if content is None:
                continue
            for operands, operator in content.operations:
                if operator == b'DP' and operands and operands[0] == self.TAG:
                    props = operands[1] if len(operands) == 2 else None
                    if not isinstance(props, DictionaryObject):
                        yield ''
                    else:
                        yield str(props.get('/Payload', ''))

    def contains_watermark_frame(self, document: bytes) -> bool:
        try:
            return any(True for _ in self._frames(self._read(document)))
        except InvalidDocumentError:
            raise
        except Exception:
            raise InvalidDocumentError('The PDF could not be parsed safely.') from None

    def embed(self, document: bytes, token: UUID) -> bytes:
        try:
            reader = self._read(document)
            if any(True for _ in self._frames(reader)):
                raise InvalidDocumentError('Upload an original without an existing PDF watermark.')
            writer = PdfWriter(clone_from=reader)
            frame = (b'\xfe\xff' + self.codec.encode(token).encode('utf-16-be')).hex().encode('ascii')
            marker = b'\n/StegaShield << /Payload <' + frame + b'> >> DP\n'
            count = min(5, len(writer.pages))
            indexes = {round(i * (len(writer.pages) - 1) / max(count - 1, 1)) for i in range(count)}
            for index in indexes:
                page = writer.pages[index]
                content = page.get_contents()
                stream = DecodedStreamObject()
                stream.set_data((content.get_data() if content is not None else b'') + marker)
                page.replace_contents(stream)
            output = BytesIO()
            writer.write(output)
            result = output.getvalue()
            if len(result) > self.MAX_BYTES:
                raise InvalidDocumentError('Protected PDF exceeds the supported size limit.')
            return result
        except InvalidDocumentError:
            raise
        except Exception:
            raise InvalidDocumentError('The PDF could not be watermarked safely.') from None

    def extract(self, document: bytes) -> ExtractedPdfWatermark | None:
        try:
            frames = list(self._frames(self._read(document)))
            decoded = [self.codec.decode(frame) for frame in frames]
            if not decoded or any(item is None for item in decoded):
                return None
            tokens = {item.token for item in decoded if item is not None}
            if len(tokens) != 1:
                return None
            return ExtractedPdfWatermark(token=tokens.pop(), valid_copies=len(decoded))
        except InvalidDocumentError:
            raise
        except Exception:
            raise InvalidDocumentError('The PDF could not be parsed safely.') from None
