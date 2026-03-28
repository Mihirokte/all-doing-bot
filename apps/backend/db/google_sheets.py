"""Google Sheets implementation for cohort data. Used when credentials are present."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from apps.backend.db.models import Entry
from apps.backend.db.sheets_retry import run_sync_with_retry

logger = logging.getLogger(__name__)

_HEADER_ENTRIES = ["entry_id", "content", "source", "metadata", "created_at"]


class GoogleSheets:
    """Sheets backend using gspread. Writes/reads cohort data to worksheets named by cohort."""

    def __init__(self) -> None:
        from apps.backend.db.google_client import get_or_create_spreadsheet
        self._spreadsheet = get_or_create_spreadsheet()

    def _worksheet(self, cohort_name: str):
        """Return worksheet for cohort (blocking)."""
        return self._spreadsheet.worksheet(cohort_name)

    def _add_entries_sync(self, cohort_name: str, entries: list[Entry]) -> None:
        ws = self._worksheet(cohort_name)
        now = datetime.now(timezone.utc).isoformat()
        raw = ws.get_all_values()
        next_id = 1
        if len(raw) > 1:
            ids = []
            for row in raw[1:]:
                if row and str(row[0]).strip().isdigit():
                    ids.append(int(row[0]))
            next_id = max(ids, default=0) + 1
        rows = []
        for e in entries:
            eid = e.entry_id if e.entry_id else next_id
            next_id += 1
            row = [
                eid,
                e.content or "",
                e.source or "",
                e.metadata if isinstance(e.metadata, str) else json.dumps(e.metadata or {}),
                e.created_at or now,
            ]
            rows.append(row)
        if rows:
            ws.append_rows(rows, value_input_option="USER_ENTERED")

    def _get_entries_sync(self, cohort_name: str, limit: int, offset: int) -> list[Entry]:
        ws = self._worksheet(cohort_name)
        raw = ws.get_all_values()
        if not raw or raw[0] != _HEADER_ENTRIES:
            if raw and raw[0] != _HEADER_ENTRIES:
                logger.warning("Cohort sheet %s has unexpected header: %s", cohort_name, raw[0][:3])
            return []
        out = []
        for row in raw[1:]:
            if len(row) < 5:
                row = row + [""] * (5 - len(row))
            entry_id = int(row[0]) if row[0] and str(row[0]).strip().isdigit() else 0
            content = row[1] if len(row) > 1 else ""
            source = row[2] if len(row) > 2 else ""
            metadata = row[3] if len(row) > 3 else "{}"
            created_at = row[4] if len(row) > 4 else ""
            out.append(
                Entry(
                    entry_id=entry_id,
                    content=content,
                    source=source,
                    metadata=metadata,
                    created_at=created_at,
                )
            )
        return out[offset : offset + limit]

    async def add_entries(self, cohort_name: str, entries: list[Entry]) -> None:
        await run_sync_with_retry(
            self._add_entries_sync,
            cohort_name,
            entries,
            operation="google_sheets.add_entries",
        )

    async def get_entries(self, cohort_name: str, limit: int = 100, offset: int = 0) -> list[Entry]:
        return await run_sync_with_retry(
            self._get_entries_sync,
            cohort_name,
            limit,
            offset,
            operation="google_sheets.get_entries",
        )
