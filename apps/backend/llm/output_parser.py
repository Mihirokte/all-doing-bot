"""Robust JSON extraction and schema validation for unreliable LLM output."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar, get_args, get_origin

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _try_json_loads(candidate: str, strategy: str, expected_type: type) -> dict | list | None:
    logger.debug("Trying JSON extraction strategy: %s", strategy)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if expected_type is list and isinstance(parsed, list):
        logger.info("JSON extraction succeeded with strategy: %s", strategy)
        return parsed
    if expected_type is dict and isinstance(parsed, dict):
        logger.info("JSON extraction succeeded with strategy: %s", strategy)
        return parsed
    if expected_type not in (dict, list):
        logger.info("JSON extraction succeeded with strategy: %s", strategy)
        return parsed
    return None


def _extract_markdown_block(raw_output: str) -> str | None:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_output.strip(), flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_balanced_json(raw_output: str) -> str | None:
    text = raw_output.strip()
    for start_char, close_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == start_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return None


def _repair_truncated_json(raw_output: str) -> str | None:
    text = raw_output.strip()
    start_idx = min([idx for idx in (text.find("{"), text.find("[")) if idx != -1], default=-1)
    if start_idx == -1:
        return None
    candidate = text[start_idx:]
    stack: list[str] = []
    in_string = False
    escape = False
    for char in candidate:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in ("}", "]") and stack and stack[-1] == char:
            stack.pop()
    if in_string:
        candidate += '"'
    while stack:
        candidate += stack.pop()
    return candidate


def _regex_key_values(raw_output: str) -> dict[str, Any] | None:
    pairs = re.findall(r'"([^"]+)"\s*:\s*("([^"\\]*(?:\\.[^"\\]*)*)"|-?\d+(?:\.\d+)?|true|false|null)', raw_output)
    if not pairs:
        return None
    result: dict[str, Any] = {}
    for key, raw_value, string_value in pairs:
        if raw_value.startswith('"'):
            result[key] = string_value
        elif raw_value in ("true", "false"):
            result[key] = raw_value == "true"
        elif raw_value == "null":
            result[key] = None
        elif "." in raw_value:
            try:
                result[key] = float(raw_value)
            except ValueError:
                result[key] = raw_value
        else:
            try:
                result[key] = int(raw_value)
            except ValueError:
                result[key] = raw_value
    return result


def extract_json(raw_output: str, expected_type: type = dict) -> dict | list | None:
    """Extract JSON from unreliable LLM text using layered recovery strategies."""
    if not raw_output or not raw_output.strip():
        logger.debug("No raw output provided for JSON extraction")
        return None

    parsed = _try_json_loads(raw_output.strip(), "direct_parse", expected_type)
    if parsed is not None:
        return parsed

    markdown_block = _extract_markdown_block(raw_output)
    if markdown_block:
        parsed = _try_json_loads(markdown_block, "markdown_block", expected_type)
        if parsed is not None:
            return parsed

    balanced = _extract_balanced_json(raw_output)
    if balanced:
        parsed = _try_json_loads(balanced, "brace_matching", expected_type)
        if parsed is not None:
            return parsed

    repaired = _repair_truncated_json(raw_output)
    if repaired:
        parsed = _try_json_loads(repaired, "greedy_repair", expected_type)
        if parsed is not None:
            return parsed

    if expected_type is dict:
        logger.debug("Trying JSON extraction strategy: key_value_regex")
        parsed_dict = _regex_key_values(raw_output)
        if parsed_dict is not None:
            logger.info("JSON extraction succeeded with strategy: key_value_regex")
            return parsed_dict

    return None


def _infer_expected_type_from_schema(schema: type[BaseModel]) -> type:
    annotation = getattr(schema, "__pydantic_root_model__", False)
    if annotation:
        return list
    return dict


def _default_for_annotation(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if annotation is str:
        return ""
    if annotation is list or origin is list:
        return []
    if annotation is dict or origin is dict:
        return {}
    if origin is not None:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if args:
            return _default_for_annotation(args[0])
    return None


def _coerce_for_schema(
    data: dict[str, Any],
    schema: type[BaseModel],
    strict_fields: set[str] | None = None,
) -> dict[str, Any]:
    corrected = dict(data)
    strict = strict_fields or set()
    for field_name, field_info in schema.model_fields.items():
        annotation = field_info.annotation
        if field_name not in corrected or corrected[field_name] is None:
            if field_name in strict:
                raise ValueError(
                    f"Required field '{field_name}' is missing from LLM output for {schema.__name__}"
                )
            default_value = _default_for_annotation(annotation)
            if default_value is not None:
                logger.warning(
                    "Coercing missing field '%s' to default %r for schema %s",
                    field_name, default_value, schema.__name__,
                )
                corrected[field_name] = default_value
            continue
        # For strict list fields, reject empty lists
        if field_name in strict:
            origin = get_origin(annotation)
            if (annotation is list or origin is list) and isinstance(corrected[field_name], list) and not corrected[field_name]:
                raise ValueError(
                    f"Required field '{field_name}' must not be empty for {schema.__name__}"
                )
        origin = get_origin(annotation)
        target = annotation
        if origin is None:
            args = [arg for arg in get_args(annotation) if arg is not type(None)]
            if args:
                target = args[0]
                origin = get_origin(target)
        if target is str and not isinstance(corrected[field_name], str):
            logger.warning(
                "Coercing field '%s' from %s to str for schema %s",
                field_name, type(corrected[field_name]).__name__, schema.__name__,
            )
            corrected[field_name] = str(corrected[field_name])
        elif (target is dict or origin is dict) and not isinstance(corrected[field_name], dict):
            logger.warning(
                "Coercing field '%s' from %s to empty dict for schema %s",
                field_name, type(corrected[field_name]).__name__, schema.__name__,
            )
            corrected[field_name] = {}
        elif (target is list or origin is list) and not isinstance(corrected[field_name], list):
            logger.warning(
                "Coercing field '%s' from %s to empty list for schema %s",
                field_name, type(corrected[field_name]).__name__, schema.__name__,
            )
            corrected[field_name] = []
    return corrected


def parse_and_validate(raw_output: str, schema: type[T]) -> T | None:
    """Extract JSON and validate against a schema, with one auto-correction pass."""
    extracted = extract_json(raw_output, expected_type=_infer_expected_type_from_schema(schema))
    if extracted is None or not isinstance(extracted, dict):
        logger.warning("No valid JSON payload extracted for schema %s", schema.__name__)
        return None
    try:
        return schema.model_validate(extracted)
    except ValidationError as first_error:
        logger.debug("Initial schema validation failed for %s: %s", schema.__name__, first_error)
        corrected = _coerce_for_schema(extracted, schema)
        try:
            return schema.model_validate(corrected)
        except ValidationError as second_error:
            logger.warning("Schema validation failed for %s after auto-correction: %s", schema.__name__, second_error)
            return None


def parse_json_output(raw: str, model: type[T]) -> T | None:
    """Backward-compatible wrapper used by older call sites."""
    return parse_and_validate(raw, model)
