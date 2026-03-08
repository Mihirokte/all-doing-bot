"""Cohort data sheets: add/get entries. In-memory fake when no Google creds."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from apps.backend.config import settings
from apps.backend.db.models import Entry

logger = logging.getLogger(__name__)


class SheetsBackend:
    """Interface for cohort sheet operations."""

    async def add_entries(self, cohort_name: str, entries: list[Entry]) -> None:
        raise NotImplementedError

    async def get_entries(self, cohort_name: str, limit: int = 100, offset: int = 0) -> list[Entry]:
        raise NotImplementedError


class FakeSheets(SheetsBackend):
    """In-memory store per cohort. For tests and when no Google creds."""

    def __init__(self) -> None:
        self._sheets: dict[str, list[Entry]] = {}
        self._next_id: dict[str, int] = {}

    async def add_entries(self, cohort_name: str, entries: list[Entry]) -> None:
        if cohort_name not in self._sheets:
            self._sheets[cohort_name] = []
            self._next_id[cohort_name] = 1
        now = datetime.now(timezone.utc).isoformat()
        for e in entries:
            entry_id = self._next_id[cohort_name]
            self._next_id[cohort_name] += 1
            stored = e.model_copy(update={"entry_id": entry_id, "created_at": e.created_at or now})
            self._sheets[cohort_name].append(stored)

    async def get_entries(self, cohort_name: str, limit: int = 100, offset: int = 0) -> list[Entry]:
        rows = self._sheets.get(cohort_name, [])
        return rows[offset : offset + limit]


def _get_sheets() -> SheetsBackend:
    if settings.credentials_path and settings.spreadsheet_id:
        try:
            from apps.backend.db.google_sheets import GoogleSheets
            return GoogleSheets()
        except Exception as e:
            logger.error("Google sheets configured but init failed: %s", e)
            raise
    return FakeSheets()


_sheets: SheetsBackend | None = None


def _sheets_instance() -> SheetsBackend:
    global _sheets
    if _sheets is None:
        _sheets = _get_sheets()
    return _sheets


async def add_entries(cohort_name: str, entries: list[Entry]) -> None:
    await _sheets_instance().add_entries(cohort_name, entries)


async def get_entries(cohort_name: str, limit: int = 100, offset: int = 0) -> list[Entry]:
    return await _sheets_instance().get_entries(cohort_name, limit=limit, offset=offset)


async def list_cohort_entries(cohort_name: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """Convenience: get entries as dicts for API response."""
    entries = await get_entries(cohort_name, limit=limit, offset=offset)
    return [
        {
            "entry_id": e.entry_id,
            "content": e.content,
            "source": e.source,
            "metadata": e.metadata,
            "created_at": e.created_at,
        }
        for e in entries
    ]
