from uuid import UUID

from pydantic import BaseModel, Field


class ExtractionResponse(BaseModel):
    found: bool
    token: UUID
    valid_copies: int = Field(ge=1)
    message: str
