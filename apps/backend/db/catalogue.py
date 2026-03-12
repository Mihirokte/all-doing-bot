"""Master catalogue: list/create/update/delete cohorts. In-memory fake when no Google creds."""
from __future__ import annotations

import logging
from typing import Any

from apps.backend.config import settings
from apps.backend.db.models import Cohort

logger = logging.getLogger(__name__)


class CatalogueBackend:
    """Interface for catalogue operations. Implementations: Google, Fake."""

    async def list_cohorts(self) -> list[Cohort]:
        raise NotImplementedError

    async def get_cohort(self, name: str) -> Cohort | None:
        raise NotImplementedError

    async def create_cohort(self, cohort: Cohort) -> None:
        raise NotImplementedError

    async def update_cohort(self, name: str, updates: dict[str, Any]) -> None:
        raise NotImplementedError

    async def delete_cohort(self, name: str) -> None:
        raise NotImplementedError


class FakeCatalogue(CatalogueBackend):
    """In-memory catalogue for tests and when GOOGLE_CREDS_PATH is not set."""

    def __init__(self) -> None:
        self._cohorts: dict[str, Cohort] = {}

    async def list_cohorts(self) -> list[Cohort]:
        return list(self._cohorts.values())

    async def get_cohort(self, name: str) -> Cohort | None:
        return self._cohorts.get(name)

    async def create_cohort(self, cohort: Cohort) -> None:
        self._cohorts[cohort.cohort_name] = cohort

    async def update_cohort(self, name: str, updates: dict[str, Any]) -> None:
        if name not in self._cohorts:
            return
        c = self._cohorts[name]
        valid_updates = {k: v for k, v in updates.items() if hasattr(c, k)}
        self._cohorts[name] = c.model_copy(update=valid_updates)

    async def delete_cohort(self, name: str) -> None:
        self._cohorts.pop(name, None)


def _get_backend() -> CatalogueBackend:
    from apps.backend.db.google_client import spreadsheet_available
    if spreadsheet_available():
        try:
            from apps.backend.db.google_catalogue import GoogleCatalogue
            return GoogleCatalogue()
        except Exception as e:
            logger.error("Google catalogue configured but init failed: %s", e)
            raise
    return FakeCatalogue()


# Singleton used by API and pipeline
catalogue = _get_backend()
