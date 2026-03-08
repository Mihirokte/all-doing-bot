"""Tests for startup logging and CORS config (mocked settings)."""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import patch

import pytest


def test_cors_origins_from_config() -> None:
    from apps.backend.config import Settings
    s = Settings(cors_allow_origins="https://a.com,https://b.com")
    assert s.cors_origins_list == ["https://a.com", "https://b.com"]


def test_cors_origins_empty_becomes_empty_list() -> None:
    from apps.backend.config import Settings
    s = Settings(cors_allow_origins="")
    assert s.cors_origins_list == []


@patch("apps.backend.main.settings")
def test_lifespan_logs_llm_and_persistence_warnings(settings_mock, caplog):
    """Startup logs or warns when mock/fake mode is in effect."""
    settings_mock.llm_provider_order = ["remote", "mock"]
    settings_mock.model_file_path = None
    settings_mock.model_path = ""
    settings_mock.remote_llm_api_key = ""
    settings_mock.spreadsheet_id = ""
    settings_mock.credentials_path = None
    settings_mock.cors_origins_list = ["http://localhost:3000"]

    from apps.backend.main import lifespan
    from fastapi import FastAPI
    app = FastAPI()

    async def run_lifespan():
        async with lifespan(app):
            pass

    with caplog.at_level(logging.INFO):
        asyncio.run(run_lifespan())
    log_text = caplog.text
    assert "provider order" in log_text or "LLM" in log_text
    assert "mock" in log_text or "Remote" in log_text or "SPREADSHEET" in log_text or "GOOGLE" in log_text


@patch("apps.backend.main.settings")
def test_lifespan_logs_google_configured_when_both_set(settings_mock, caplog, tmp_path):
    settings_mock.llm_provider_order = ["remote", "mock"]
    settings_mock.model_file_path = None
    settings_mock.model_path = ""
    settings_mock.remote_llm_api_key = "key"
    settings_mock.spreadsheet_id = "id"
    settings_mock.credentials_path = tmp_path
    settings_mock.cors_origins_list = []

    from apps.backend.main import lifespan
    from fastapi import FastAPI
    app = FastAPI()

    async def run_lifespan():
        async with lifespan(app):
            pass

    with caplog.at_level(logging.INFO):
        asyncio.run(run_lifespan())
    assert "Google persistence" in caplog.text or "SPREADSHEET" in caplog.text
