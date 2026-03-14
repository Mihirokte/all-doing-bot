"""Action contracts: versioned capability schema, error taxonomy, retry policy, idempotency keys."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Taxonomy of action failures for retry and dead-letter routing."""

    # Transient: retry with backoff
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"

    # Input/validation: do not retry same payload
    INVALID_INPUT = "invalid_input"
    MISSING_PARAM = "missing_param"
    SCHEMA_VIOLATION = "schema_violation"

    # External dependency: retry may help
    EXTERNAL_ERROR = "external_error"
    AUTH_FAILED = "auth_failed"

    # Permanent: send to dead letter
    UNKNOWN_ACTION = "unknown_action"
    PERMANENT_FAILURE = "permanent_failure"
    INTERNAL = "internal"


class RetryClass(str, Enum):
    """Whether and how to retry an action step."""

    RETRY_TRANSIENT = "retry_transient"  # backoff, cap at N
    RETRY_ONCE = "retry_once"
    NO_RETRY = "no_retry"


class ActionContract(BaseModel):
    """Versioned contract envelope for an action capability."""

    capability_id: str = Field(..., description="Unique action type, e.g. web_fetch, search_web")
    version: str = Field(default="1", description="Contract version for compatibility")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema subset for params")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for list[Entry] shape")
    default_retry_class: RetryClass = Field(default=RetryClass.RETRY_TRANSIENT)
    error_code_map: dict[str, ErrorCode] = Field(
        default_factory=dict,
        description="Map exception type or message substring -> ErrorCode",
    )


def error_code_from_exception(exc: BaseException) -> ErrorCode:
    """Map a raised exception to an ErrorCode for retry/DeadLetter routing."""
    msg = (getattr(exc, "message", None) or str(exc)).lower()
    if "timeout" in msg or "timed out" in msg:
        return ErrorCode.TIMEOUT
    if "rate limit" in msg or "429" in msg:
        return ErrorCode.RATE_LIMIT
    if "connection" in msg or "network" in msg or "refused" in msg:
        return ErrorCode.NETWORK
    if "unavailable" in msg or "503" in msg or "502" in msg:
        return ErrorCode.UNAVAILABLE
    if "auth" in msg or "401" in msg or "403" in msg:
        return ErrorCode.AUTH_FAILED
    if "validation" in msg or "invalid" in msg or "required" in msg:
        return ErrorCode.INVALID_INPUT
    return ErrorCode.EXTERNAL_ERROR


def retry_class_for_error(code: ErrorCode, contract: ActionContract | None) -> RetryClass:
    """Return retry policy for this error; contract can override default."""
    if contract and code.name in contract.error_code_map:
        # If we add ErrorCode -> RetryClass on contract, use it here
        pass
    if code in (
        ErrorCode.NETWORK,
        ErrorCode.RATE_LIMIT,
        ErrorCode.TIMEOUT,
        ErrorCode.UNAVAILABLE,
        ErrorCode.EXTERNAL_ERROR,
    ):
        return RetryClass.RETRY_TRANSIENT
    if code in (ErrorCode.INVALID_INPUT, ErrorCode.MISSING_PARAM, ErrorCode.SCHEMA_VIOLATION):
        return RetryClass.NO_RETRY
    if code in (ErrorCode.UNKNOWN_ACTION, ErrorCode.PERMANENT_FAILURE, ErrorCode.INTERNAL):
        return RetryClass.NO_RETRY
    return RetryClass.RETRY_TRANSIENT


def idempotency_key(run_id: str, step_index: int, action: str, params: dict[str, Any]) -> str:
    """
    Build a dedupe key for a step so workers can skip duplicate processing.
    Uses run_id + step_index + action + stable param fingerprint (e.g. sorted JSON).
    """
    import hashlib
    import json

    try:
        fp = json.dumps(params, sort_keys=True, default=str)
    except (TypeError, ValueError):
        fp = repr(params)
    h = hashlib.sha256(f"{run_id}:{step_index}:{action}:{fp}".encode()).hexdigest()
    return f"idem:{h[:24]}"


# Default contracts for built-in actions (capability_id matches registry key).
DEFAULT_CONTRACTS: dict[str, ActionContract] = {
    "web_fetch": ActionContract(
        capability_id="web_fetch",
        version="1",
        input_schema={
            "type": "object",
            "properties": {"urls": {"type": "array", "items": {"type": "string"}}, "url": {"type": "string"}},
        },
        default_retry_class=RetryClass.RETRY_TRANSIENT,
    ),
    "search_web": ActionContract(
        capability_id="search_web",
        version="1",
        input_schema={
            "type": "object",
            "properties": {"q": {"type": "string"}, "query": {"type": "string"}, "top_n": {"type": "integer"}},
        },
        default_retry_class=RetryClass.RETRY_TRANSIENT,
    ),
    "api_call": ActionContract(
        capability_id="api_call",
        version="1",
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string"}, "urls": {"type": "array"}, "method": {"type": "string"}},
        },
        default_retry_class=RetryClass.RETRY_TRANSIENT,
    ),
    "transform": ActionContract(
        capability_id="transform",
        version="1",
        input_schema={"type": "object"},
        default_retry_class=RetryClass.NO_RETRY,
    ),
    "browser_automation": ActionContract(
        capability_id="browser_automation",
        version="1",
        input_schema={
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}},
                "url": {"type": "string"},
                "q": {"type": "string"},
                "query": {"type": "string"},
            },
        },
        default_retry_class=RetryClass.RETRY_TRANSIENT,
    ),
}
