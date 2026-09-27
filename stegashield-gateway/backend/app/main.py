from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Loading settings here makes unsafe or missing production configuration
    # fail before the API accepts requests.
    get_settings()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Secure document watermarking and forensic extraction API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
