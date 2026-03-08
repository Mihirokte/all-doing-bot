"""Tests for api_call and transform actions with mocked HTTP."""
from __future__ import annotations

import asyncio

import pytest
import respx
from httpx import Response

from apps.backend.actions.api_call import ApiCallAction
from apps.backend.actions.transform import TransformAction


@respx.mock
def test_api_call_returns_entries_from_http() -> None:
    respx.get("https://api.example.com/data").mock(return_value=Response(200, text="hello world"))
    action = ApiCallAction()
    entries = asyncio.run(action.execute({"url": "https://api.example.com/data"}))
    assert len(entries) == 1
    assert entries[0].content == "hello world"
    assert entries[0].source == "https://api.example.com/data"
    assert "status_code" in entries[0].metadata
    assert "200" in entries[0].metadata


@respx.mock
def test_api_call_urls_multiple() -> None:
    respx.get("https://a.example/1").mock(return_value=Response(200, text="one"))
    respx.get("https://a.example/2").mock(return_value=Response(200, text="two"))
    action = ApiCallAction()
    entries = asyncio.run(action.execute({"urls": ["https://a.example/1", "https://a.example/2"]}))
    assert len(entries) == 2
    assert entries[0].content == "one"
    assert entries[1].content == "two"


def test_api_call_requires_url() -> None:
    action = ApiCallAction()
    with pytest.raises(ValueError, match="url"):
        asyncio.run(action.execute({}))


def test_api_call_invalid_method() -> None:
    action = ApiCallAction()
    with pytest.raises(ValueError, match="method"):
        asyncio.run(action.execute({"url": "https://x.example/", "method": "INVALID"}))


@respx.mock
def test_api_call_failure_recorded_as_entry() -> None:
    respx.get("https://fail.example/").mock(return_value=Response(500, text="server error"))
    action = ApiCallAction()
    entries = asyncio.run(action.execute({"url": "https://fail.example/"}))
    assert len(entries) == 1
    assert "500" in entries[0].content or "error" in entries[0].content.lower()


def test_transform_list_produces_entries() -> None:
    action = TransformAction()
    entries = asyncio.run(action.execute({"input": [{"a": 1}, {"a": 2}]}))
    assert len(entries) == 2
    assert '{"a": 1}' in entries[0].content or "1" in entries[0].content
    assert entries[0].source == "transform"


def test_transform_dict_one_entry() -> None:
    action = TransformAction()
    entries = asyncio.run(action.execute({"data": {"key": "value"}}))
    assert len(entries) == 1
    assert "key" in entries[0].content and "value" in entries[0].content


def test_transform_field_extracts_content() -> None:
    action = TransformAction()
    entries = asyncio.run(action.execute({"input": [{"body": "only this"}], "field": "body"}))
    assert len(entries) == 1
    assert entries[0].content == "only this"


def test_transform_requires_input() -> None:
    action = TransformAction()
    with pytest.raises(ValueError, match="input"):
        asyncio.run(action.execute({}))
