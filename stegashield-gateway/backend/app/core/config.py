from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    pdf_enabled: bool = False
    app_name: str = "StegaShield Gateway"
    api_v1_prefix: str = "/api/v1"
    max_upload_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    watermark_secret: str = Field(min_length=32)
    allowed_origins: list[str] | str = ["http://localhost:5173"]
    supabase_url: str = ""
    supabase_publishable_key: str = Field(default="", repr=False)
    supabase_jwt_issuer: str = ""
    supabase_secret_key: str = Field(default="", repr=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def reject_unsafe_production_secret(self) -> "Settings":
        if self.app_env.lower() == "production" and "replace-this" in self.watermark_secret.lower():
            raise ValueError("Production requires a randomly generated WATERMARK_SECRET.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
