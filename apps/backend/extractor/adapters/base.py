"""Base extractor adapter and normalized extraction result."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """Normalized result for any extracted URL."""

    url: str
    title: str
    content: str
    content_type: str
    items: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    extracted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    adapter_used: str


class BaseAdapter(ABC):
    """Each adapter converts a URL into clean markdown text."""

    adapter_name = "base"

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this adapter handles the given URL."""

    @abstractmethod
    async def extract(self, url: str, max_chars: int = 2000) -> ExtractionResult:
        """Fetch and clean the URL content."""
