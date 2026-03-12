"""Shared Google Drive + Sheets client: resolve spreadsheet by ID or by name (find or create)."""
from __future__ import annotations

import logging
from typing import Any

from apps.backend.config import settings

logger = logging.getLogger(__name__)


def _get_creds():
    from google.oauth2.service_account import Credentials
    creds_path = settings.credentials_path
    if not creds_path:
        raise ValueError("GOOGLE_CREDS_PATH is not set or file not found")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    return Credentials.from_service_account_file(str(creds_path), scopes=scopes)


def get_gspread_client():
    """Return authorized gspread client (Drive + Sheets APIs)."""
    import gspread
    creds = _get_creds()
    return gspread.authorize(creds)


def get_or_create_spreadsheet():
    """
    Return the spreadsheet to use: by SPREADSHEET_ID if set, else by name (find or create).
    Uses Drive API (list by name) and Sheets API (create/open) via gspread.
    """
    client = get_gspread_client()
    if settings.spreadsheet_id:
        return client.open_by_key(settings.spreadsheet_id)
    name = (settings.google_sheets_spreadsheet_name or "").strip()
    if not name:
        raise ValueError(
            "SPREADSHEET_ID or GOOGLE_SHEETS_SPREADSHEET_NAME must be set"
        )
    try:
        from gspread.exceptions import SpreadsheetNotFound
    except ImportError:
        SpreadsheetNotFound = Exception  # fallback if module structure changes
    try:
        spreadsheet = client.open(name)
        logger.info("Using existing Google Sheet: %s (id=%s)", name, spreadsheet.id)
        return spreadsheet
    except SpreadsheetNotFound:
        pass
    spreadsheet = client.create(name)
    logger.info("Created new Google Sheet: %s (id=%s)", name, spreadsheet.id)
    return spreadsheet


def spreadsheet_available() -> bool:
    """True if credentials and either spreadsheet_id or spreadsheet_name are set."""
    if not settings.credentials_path:
        return False
    if settings.spreadsheet_id:
        return True
    return bool((settings.google_sheets_spreadsheet_name or "").strip())
