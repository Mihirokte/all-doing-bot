"""Abstract base action: execute(params) -> list[Entry]."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from apps.backend.db.models import Entry


class BaseAction(ABC):
    """Action implementations return structured entries for the cohort sheet."""

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        ...
