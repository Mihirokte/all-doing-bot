"""Abstract base action: execute(params) -> list[Entry]. Contract metadata optional."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

from apps.backend.db.models import Entry

if TYPE_CHECKING:
    from apps.backend.actions.contracts import ActionContract


class BaseAction(ABC):
    """Action implementations return structured entries for the cohort sheet."""

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        ...

    def get_contract(self) -> ActionContract | None:
        """Override to supply contract; otherwise registry uses DEFAULT_CONTRACTS by capability_id."""
        return None
