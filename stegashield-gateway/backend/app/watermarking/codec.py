import hashlib
import hmac
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DecodedWatermark:
    token: UUID


class SignedWatermarkCodec:
    """Encode a UUID plus truncated HMAC into invisible Unicode characters."""

    MAGIC = b"SS1"
    SIGNATURE_SIZE = 16
    START = "\u2063\u200b\u2063\u200c\u2063"
    END = "\u2063\u200d\u2063\u2060\u2063"
    SYMBOLS = ("\u200b", "\u200c", "\u200d", "\u2060")
    REVERSE = {symbol: index for index, symbol in enumerate(SYMBOLS)}

    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValueError("The watermark secret must contain at least 32 bytes.")
        self._secret = secret

    def encode(self, token: UUID) -> str:
        body = self.MAGIC + token.bytes
        signature = hmac.new(self._secret, body, hashlib.sha256).digest()[: self.SIGNATURE_SIZE]
        payload = body + signature
        symbols: list[str] = []
        for byte in payload:
            symbols.extend(self.SYMBOLS[(byte >> shift) & 0b11] for shift in (6, 4, 2, 0))
        return self.START + "".join(symbols) + self.END

    def decode(self, framed_text: str) -> DecodedWatermark | None:
        if not framed_text.startswith(self.START) or not framed_text.endswith(self.END):
            return None
        encoded = framed_text[len(self.START) : -len(self.END)]
        expected_bytes = len(self.MAGIC) + 16 + self.SIGNATURE_SIZE
        if len(encoded) != expected_bytes * 4:
            return None
        try:
            values = [self.REVERSE[character] for character in encoded]
        except KeyError:
            return None
        raw = bytes(
            (values[index] << 6)
            | (values[index + 1] << 4)
            | (values[index + 2] << 2)
            | values[index + 3]
            for index in range(0, len(values), 4)
        )
        body, provided_signature = raw[:-self.SIGNATURE_SIZE], raw[-self.SIGNATURE_SIZE :]
        expected_signature = hmac.new(self._secret, body, hashlib.sha256).digest()[: self.SIGNATURE_SIZE]
        if not hmac.compare_digest(provided_signature, expected_signature):
            return None
        if not body.startswith(self.MAGIC):
            return None
        try:
            return DecodedWatermark(token=UUID(bytes=body[len(self.MAGIC) :]))
        except ValueError:
            return None

    def find_frames(self, text: str) -> list[str]:
        frames: list[str] = []
        cursor = 0
        while True:
            start = text.find(self.START, cursor)
            if start < 0:
                break
            end = text.find(self.END, start + len(self.START))
            if end < 0:
                break
            end += len(self.END)
            frames.append(text[start:end])
            cursor = end
        return frames
