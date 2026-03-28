"""Google Sheets implementation of catalogue. Used when credentials are present."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from apps.backend.config import settings
from apps.backend.db.models import Cohort
from apps.backend.db.sheets_retry import run_sync_with_retry

logger = logging.getLogger(__name__)

_CATALOGUE_SHEET = "_catalogue"
_CATALOGUE_HEADERS = [
    "cohort_name", "cohort_description", "action_type", "action_params",
    "created_at", "last_run", "sheet_name", "entry_count",
]


class GoogleCatalogue:
    """Catalogue backed by Google Sheets _catalogue sheet."""

    def __init__(self) -> None:
        from apps.backend.db.google_client import get_or_create_spreadsheet
        self._spreadsheet = get_or_create_spreadsheet()
        self._ensure_catalogue_sheet()

    def _ensure_catalogue_sheet(self) -> None:
        try:
            self._spreadsheet.worksheet(_CATALOGUE_SHEET)
        except Exception:
            ws = self._spreadsheet.add_worksheet(_CATALOGUE_SHEET, rows=1000, cols=len(_CATALOGUE_HEADERS))
            ws.append_row(_CATALOGUE_HEADERS, value_input_option="USER_ENTERED")

    def _catalogue_worksheet(self):
        return self._spreadsheet.worksheet(_CATALOGUE_SHEET)

    def _row_to_cohort(self, row: list[Any]) -> Cohort:
        while len(row) < len(_CATALOGUE_HEADERS):
            row.append("")
        return Cohort(
            cohort_name=str(row[0] or ""),
            cohort_description=str(row[1] or ""),
            action_type=str(row[2] or "web_fetch"),
            action_params=str(row[3] or "{}"),
            created_at=str(row[4] or ""),
            last_run=str(row[5] or ""),
            sheet_name=str(row[6] or ""),
            entry_count=int(row[7]) if row[7] is not None and str(row[7]).strip().isdigit() else 0,
        )

    def _cohort_to_row(self, c: Cohort) -> list[Any]:
        return [
            c.cohort_name,
            c.cohort_description,
            c.action_type,
            c.action_params,
            c.created_at,
            c.last_run,
            c.sheet_name or c.cohort_name,
            c.entry_count,
        ]

    def _list_cohorts_sync(self) -> list[Cohort]:
        ws = self._catalogue_worksheet()
        raw = ws.get_all_values()
        if not raw or raw[0] != _CATALOGUE_HEADERS:
            return []
        return [self._row_to_cohort(row) for row in raw[1:] if row and str(row[0] or "").strip()]

    def _get_cohort_sync(self, name: str) -> Cohort | None:
        for c in self._list_cohorts_sync():
            if c.cohort_name == name:
                return c
        return None

    def _create_cohort_sync(self, cohort: Cohort) -> None:
        ws = self._catalogue_worksheet()
        ws.append_row(self._cohort_to_row(cohort), value_input_option="USER_ENTERED")
        sheet_name = cohort.sheet_name or cohort.cohort_name
        try:
            self._spreadsheet.worksheet(sheet_name)
        except Exception:
            self._spreadsheet.add_worksheet(sheet_name, rows=1000, cols=10)
            new_ws = self._spreadsheet.worksheet(sheet_name)
            new_ws.append_row(["entry_id", "content", "source", "metadata", "created_at"], value_input_option="USER_ENTERED")

    def _update_cohort_sync(self, name: str, updates: dict[str, Any]) -> None:
        ws = self._catalogue_worksheet()
        raw = ws.get_all_values()
        if not raw or raw[0] != _CATALOGUE_HEADERS:
            return
        name_col_idx = 0
        for i, row in enumerate(raw[1:], start=2):
            if not row or str(row[0] or "").strip() != name:
                continue
            for key, value in updates.items():
                if key not in _CATALOGUE_HEADERS:
                    continue
                col_idx = _CATALOGUE_HEADERS.index(key)
                ws.update_cell(i, col_idx + 1, value)
            return

    def _delete_cohort_sync(self, name: str) -> None:
        cohort = self._get_cohort_sync(name)
        if not cohort:
            return
        ws = self._catalogue_worksheet()
        raw = ws.get_all_values()
        if not raw or raw[0] != _CATALOGUE_HEADERS:
            return
        row_index = None
        for i, row in enumerate(raw[1:], start=2):
            if row and str(row[0] or "").strip() == name:
                row_index = i
                break
        if row_index is not None:
            ws.delete_rows(row_index)
        sheet_name = cohort.sheet_name or cohort.cohort_name
        try:
            cohort_ws = self._spreadsheet.worksheet(sheet_name)
            self._spreadsheet.del_worksheet(cohort_ws)
        except Exception as e:
            logger.warning("Could not delete worksheet %s: %s", sheet_name, e)

    async def list_cohorts(self) -> list[Cohort]:
        return await run_sync_with_retry(self._list_cohorts_sync, operation="google_catalogue.list_cohorts")

    async def get_cohort(self, name: str) -> Cohort | None:
        return await run_sync_with_retry(self._get_cohort_sync, name, operation="google_catalogue.get_cohort")

    async def create_cohort(self, cohort: Cohort) -> None:
        await run_sync_with_retry(self._create_cohort_sync, cohort, operation="google_catalogue.create_cohort")

    async def update_cohort(self, name: str, updates: dict[str, Any]) -> None:
        await run_sync_with_retry(
            self._update_cohort_sync, name, updates, operation="google_catalogue.update_cohort"
        )

    async def delete_cohort(self, name: str) -> None:
        await run_sync_with_retry(self._delete_cohort_sync, name, operation="google_catalogue.delete_cohort")
