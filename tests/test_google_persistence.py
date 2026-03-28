"""Tests for Google Sheets and Google Catalogue with mocked gspread."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.db.models import Cohort, Entry


def _mock_worksheet(initial_rows: list[list] | None = None):
    rows = list(initial_rows) if initial_rows else []

    def get_all_values():
        return list(rows)

    def append_row(values, value_input_option=None):
        rows.append(list(values))

    def append_rows(values_list, value_input_option=None):
        rows.extend(values_list)

    def update_cell(row, col, value):
        while len(rows) < row:
            rows.append([])
        r = row - 1
        while len(rows[r]) < col:
            rows[r].append("")
        rows[r][col - 1] = value

    def delete_rows(row_index):
        if 1 <= row_index <= len(rows):
            rows.pop(row_index - 1)

    ws = MagicMock()
    ws.get_all_values = get_all_values
    ws.append_row = append_row
    ws.append_rows = append_rows
    ws.update_cell = update_cell
    ws.delete_rows = delete_rows
    return ws, rows


def _mock_spreadsheet():
    worksheets = {}
    catalogue_rows = []

    def worksheet(title):
        if title not in worksheets:
            if title == "_catalogue":
                ws, _ = _mock_worksheet([["cohort_name", "cohort_description", "action_type", "action_params", "created_at", "last_run", "sheet_name", "entry_count"]])
            else:
                ws, _ = _mock_worksheet([["entry_id", "content", "source", "metadata", "created_at"]])
            worksheets[title] = ws
        return worksheets[title]

    def add_worksheet(title, rows=1000, cols=10):
        ws, _ = _mock_worksheet([["entry_id", "content", "source", "metadata", "created_at"]])
        worksheets[title] = ws
        return ws

    def del_worksheet(ws):
        pass

    spread = MagicMock()
    spread.worksheet = worksheet
    spread.add_worksheet = add_worksheet
    spread.del_worksheet = del_worksheet
    return spread


@patch("apps.backend.db.google_client.get_or_create_spreadsheet")
def test_google_sheets_retries_transient_failure(get_spreadsheet_mock):
    spread = _mock_spreadsheet()
    spread.worksheet("cohort_a")
    get_spreadsheet_mock.return_value = spread

    from apps.backend.db.google_sheets import GoogleSheets

    gs = GoogleSheets()
    attempts = {"n": 0}
    orig = gs._add_entries_sync

    def flaky(name, entries):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise Exception("503 Service Unavailable")
        return orig(name, entries)

    gs._add_entries_sync = flaky
    entries = [
        Entry(content="retry_ok", source="s", metadata="{}", created_at="2025-01-01T00:00:00Z"),
    ]
    asyncio.run(gs.add_entries("cohort_a", entries))
    assert attempts["n"] == 3
    got = asyncio.run(gs.get_entries("cohort_a", limit=10, offset=0))
    assert any(e.content == "retry_ok" for e in got)


@patch("apps.backend.db.google_client.get_or_create_spreadsheet")
def test_google_sheets_add_and_get_entries(get_spreadsheet_mock, tmp_path):
    spread = _mock_spreadsheet()
    spread.worksheet("cohort_a")  # create cohort sheet with header
    get_spreadsheet_mock.return_value = spread

    from apps.backend.db.google_sheets import GoogleSheets

    gs = GoogleSheets()
    entries = [
        Entry(content="c1", source="s1", metadata="{}", created_at="2025-01-01T00:00:00Z"),
        Entry(content="c2", source="s2", metadata='{"x":1}', created_at="2025-01-01T00:00:00Z"),
    ]
    asyncio.run(gs.add_entries("cohort_a", entries))
    ws = spread.worksheet("cohort_a")
    raw = ws.get_all_values()
    assert len(raw) >= 2 + 1  # header + 2 entries
    assert any("c1" in str(row) for row in raw)
    assert any("c2" in str(row) for row in raw)

    got = asyncio.run(gs.get_entries("cohort_a", limit=10, offset=0))
    assert len(got) >= 2
    contents = [e.content for e in got]
    assert "c1" in contents
    assert "c2" in contents


@patch("apps.backend.db.google_client.get_or_create_spreadsheet")
def test_google_catalogue_crud(get_spreadsheet_mock, tmp_path):
    spread = _mock_spreadsheet()
    get_spreadsheet_mock.return_value = spread

    from apps.backend.db.google_catalogue import GoogleCatalogue

    cat = GoogleCatalogue()
    cohort = Cohort(
        cohort_name="test_cohort",
        cohort_description="desc",
        action_type="web_fetch",
        action_params="{}",
        created_at="2025-01-01",
        last_run="",
        sheet_name="test_cohort",
        entry_count=0,
    )
    asyncio.run(cat.create_cohort(cohort))
    listed = asyncio.run(cat.list_cohorts())
    assert any(c.cohort_name == "test_cohort" for c in listed)
    got = asyncio.run(cat.get_cohort("test_cohort"))
    assert got is not None
    assert got.cohort_name == "test_cohort"
    asyncio.run(cat.update_cohort("test_cohort", {"entry_count": 5}))
    got2 = asyncio.run(cat.get_cohort("test_cohort"))
    assert got2 is not None
    assert got2.entry_count == 5
    asyncio.run(cat.delete_cohort("test_cohort"))
    got3 = asyncio.run(cat.get_cohort("test_cohort"))
    assert got3 is None


@patch("apps.backend.db.google_client.settings")
def test_google_catalogue_raises_when_creds_missing(settings_mock):
    settings_mock.credentials_path = None
    settings_mock.spreadsheet_id = "id"
    with pytest.raises(ValueError, match="GOOGLE_CREDS_PATH"):
        from apps.backend.db.google_client import get_or_create_spreadsheet
        get_or_create_spreadsheet()


@patch("apps.backend.db.google_client.get_gspread_client")
@patch("apps.backend.db.google_client.settings")
def test_google_catalogue_raises_when_spreadsheet_id_and_name_missing(settings_mock, get_client_mock, tmp_path):
    get_client_mock.return_value = MagicMock()
    settings_mock.spreadsheet_id = ""
    settings_mock.google_sheets_spreadsheet_name = ""
    with pytest.raises(ValueError, match="SPREADSHEET_ID or GOOGLE_SHEETS_SPREADSHEET_NAME"):
        from apps.backend.db.google_client import get_or_create_spreadsheet
        get_or_create_spreadsheet()
