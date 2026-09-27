from abc import ABC, abstractmethod
from uuid import UUID


class WatermarkAdapter(ABC):
    @abstractmethod
    def embed(self, document: bytes, token: UUID) -> bytes:
        """Return a protected copy without mutating the original bytes."""

    @abstractmethod
    def extract(self, document: bytes):
        """Return the verified embedded token, or None when absent."""
