from uuid import uuid4

from backend.app.watermarking.codec import SignedWatermarkCodec


SECRET = b"a-secure-test-secret-with-at-least-32-bytes"


def test_codec_round_trip() -> None:
    codec = SignedWatermarkCodec(SECRET)
    token = uuid4()
    decoded = codec.decode(codec.encode(token))
    assert decoded is not None
    assert decoded.token == token


def test_tampered_watermark_is_rejected() -> None:
    codec = SignedWatermarkCodec(SECRET)
    encoded = codec.encode(uuid4())
    body_index = len(codec.START) + 8
    replacement = codec.SYMBOLS[(codec.REVERSE[encoded[body_index]] + 1) % 4]
    tampered = encoded[:body_index] + replacement + encoded[body_index + 1 :]
    assert codec.decode(tampered) is None


def test_plain_text_contains_no_watermark() -> None:
    codec = SignedWatermarkCodec(SECRET)
    assert codec.find_frames("ordinary visible text") == []
