"""LLM parser and provider fallback tests. No real model or network required."""
from __future__ import annotations

import asyncio

from apps.backend.llm.engine import LLMEngine, LLMProvider, MockProvider
from apps.backend.llm.output_parser import extract_json, parse_and_validate
from apps.backend.models.schemas import ParsedIntent


def test_extract_json_clean_json() -> None:
    raw = '{"cohort_name":"demo","cohort_description":"desc","action_type":"web_fetch","action_params":{},"summary":"ok"}'
    parsed = extract_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["cohort_name"] == "demo"


def test_extract_json_markdown_block() -> None:
    raw = '```json\n{"cohort_name":"demo","cohort_description":"desc","action_type":"web_fetch","action_params":{},"summary":"ok"}\n```'
    parsed = extract_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["summary"] == "ok"


def test_extract_json_with_prose() -> None:
    raw = 'Here is the answer:\n{"cohort_name":"demo","cohort_description":"desc","action_type":"web_fetch","action_params":{},"summary":"ok"}\nThanks.'
    parsed = extract_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["action_type"] == "web_fetch"


def test_extract_json_truncated_json_repaired() -> None:
    raw = '{"cohort_name":"demo","cohort_description":"desc","action_type":"web_fetch","action_params":{},"summary":"ok"'
    parsed = extract_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["cohort_name"] == "demo"


def test_parse_and_validate_wrong_field_types_autocorrects() -> None:
    raw = '{"cohort_name": 123, "cohort_description": 456, "action_type": "web_fetch", "action_params": {}, "summary": 789}'
    parsed = parse_and_validate(raw, ParsedIntent)
    assert parsed is not None
    assert parsed.cohort_name == "123"
    assert parsed.summary == "789"


def test_parse_and_validate_missing_required_fields_autofills() -> None:
    raw = '{"cohort_name":"demo","action_type":"web_fetch"}'
    parsed = parse_and_validate(raw, ParsedIntent)
    assert parsed is not None
    assert parsed.cohort_description == ""
    assert parsed.action_params == {}
    assert parsed.summary == ""


def test_extract_json_complete_garbage_returns_none() -> None:
    assert extract_json("lorem ipsum definitely not json") is None


def test_extract_json_empty_string_returns_none() -> None:
    assert extract_json("") is None


def test_extract_json_nested_objects() -> None:
    raw = '{"outer":{"inner":{"value":1}},"items":[{"name":"a"}]}'
    parsed = extract_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["outer"]["inner"]["value"] == 1


def test_extract_json_array_output() -> None:
    raw = '[{"name":"a"},{"name":"b"}]'
    parsed = extract_json(raw, expected_type=list)
    assert isinstance(parsed, list)
    assert parsed[1]["name"] == "b"


def test_extract_json_key_value_fallback() -> None:
    raw = 'cohort payload => "cohort_name": "demo", "cohort_description": "desc", "action_type": "web_fetch", "summary": "ok"'
    parsed = extract_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["cohort_name"] == "demo"


def test_llm_engine_provider_fallback_to_mock() -> None:
    class FailingProvider(LLMProvider):
        provider_name = "failing"

        async def generate(self, prompt: str, max_tokens: int = 256, json_mode: bool = True) -> str:
            raise RuntimeError("boom")

    engine = LLMEngine()
    engine.providers = [FailingProvider(), MockProvider()]
    raw = asyncio.run(engine.generate("Respond in JSON only with cohort_name", json_mode=True))
    assert '"cohort_name"' in raw


def test_generate_structured_uses_mock_provider() -> None:
    engine = LLMEngine()
    engine.providers = [MockProvider()]
    parsed = asyncio.run(
        engine.generate_structured(
            'System: You extract structured intent from user queries. Respond in JSON only.\nUser: test',
            ParsedIntent,
        )
    )
    assert parsed is not None
    assert parsed.cohort_name == "test_cohort"
