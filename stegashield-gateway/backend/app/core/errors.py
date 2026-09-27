from typing import Any


class StegaShieldError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "stegashield_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class InvalidDocumentError(StegaShieldError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422, code="invalid_document")


class WatermarkNotFoundError(StegaShieldError):
    def __init__(self, message: str = "No valid StegaShield watermark was found."):
        super().__init__(message, status_code=404, code="watermark_not_found")


def register_exception_handlers(app: Any) -> None:
    # Keep the domain exceptions importable by the watermarking engine even in
    # isolated/offline tests where the web framework is not installed yet.
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(StegaShieldError)
    async def handle_stegashield_error(_: Request, exc: StegaShieldError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
