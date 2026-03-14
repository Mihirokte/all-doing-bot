"""Connector abstractions for OpenClaw-style capability routing."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from apps.backend.db.models import Entry


class BaseConnector(ABC):
    """Typed connector contract for a capability provider."""

    connector_id: str = "base_connector"
    capability_id: str = "base_capability"
    provider_key: str = "default"

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        """Execute capability through this provider."""
        ...

