from dataclasses import dataclass
from uuid import UUID, uuid4

from backend.app.core.config import Settings, get_settings
from backend.app.watermarking.codec import SignedWatermarkCodec
from backend.app.watermarking.docx_adapter import DocxWatermarkAdapter, ExtractedDocxWatermark
from backend.app.watermarking.pdf_adapter import PdfWatermarkAdapter


@dataclass(frozen=True)
class EmbeddedDocument:
    document: bytes
    token: UUID


class DocumentWatermarkService:
    def __init__(self, docx_adapter: DocxWatermarkAdapter):
        self.docx_adapter = docx_adapter
        self.pdf_adapter = PdfWatermarkAdapter(docx_adapter.codec)

    def adapter(self, format: str):
        if format == "docx":
            return self.docx_adapter
        if format == "pdf":
            return self.pdf_adapter
        raise ValueError("Unsupported document format")

    def embed(self, document: bytes, format: str) -> EmbeddedDocument:
        token = uuid4()
        return EmbeddedDocument(self.adapter(format).embed(document, token), token)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "DocumentWatermarkService":
        current = settings or get_settings()
        codec = SignedWatermarkCodec(current.watermark_secret.encode("utf-8"))
        return cls(DocxWatermarkAdapter(codec))

    def embed_docx(self, document: bytes, token: UUID | None = None) -> EmbeddedDocument:
        watermark_token = token or uuid4()
        protected = self.docx_adapter.embed(document, watermark_token)
        return EmbeddedDocument(document=protected, token=watermark_token)

    def extract_docx(self, document: bytes) -> ExtractedDocxWatermark | None:
        return self.docx_adapter.extract(document)
