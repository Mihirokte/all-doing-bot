# Action Contracts

Action execution in the pipeline follows a **versioned contract envelope** so orchestration, workers, and observability can treat all capabilities uniformly.

## Contract envelope

Each action is described by an `ActionContract`:

| Field | Description |
|-------|-------------|
| `capability_id` | Unique action type (e.g. `web_fetch`, `search_web`). Matches registry key. |
| `version` | Contract version for compatibility (e.g. `"1"`). |
| `input_schema` | JSON Schema subset for `params` passed to `execute(params)`. |
| `output_schema` | JSON Schema for the shape of returned `list[Entry]` (optional). |
| `default_retry_class` | How to retry on generic failure: `retry_transient`, `retry_once`, `no_retry`. |
| `error_code_map` | Optional map from exception type or message substring → `ErrorCode`. |

Defined in: `apps/backend/actions/contracts.py`. Default contracts for built-in actions are in `DEFAULT_CONTRACTS`.

## Error taxonomy

`ErrorCode` classifies failures for retry and dead-letter routing:

| Code | Meaning | Typical retry |
|------|----------|----------------|
| `NETWORK`, `RATE_LIMIT`, `TIMEOUT`, `UNAVAILABLE`, `EXTERNAL_ERROR` | Transient | Yes (backoff) |
| `INVALID_INPUT`, `MISSING_PARAM`, `SCHEMA_VIOLATION` | Bad input | No |
| `UNKNOWN_ACTION`, `PERMANENT_FAILURE`, `INTERNAL` | Unrecoverable | No (dead letter) |
| `AUTH_FAILED` | Credentials / permission | Config-dependent |

`retry_class_for_error(code, contract)` returns `RetryClass` for a given `ErrorCode`; contract overrides can be added later.

## Idempotency keys

Step execution is deduplicated using:

```text
idempotency_key(run_id, step_index, action, params) -> str
```

- Built from `run_id`, step index, action name, and a stable JSON fingerprint of `params`.
- Workers should check this key before executing; if the key was already processed successfully, skip or return cached result.
- Enables safe replay and restarts without double-applying the same step.

## Usage

- **Registry**: `get_contract(capability_id)` returns the contract for a capability; used by orchestrator and workers.
- **Execution**: Before calling `execute(params)`, optional validation can run against `input_schema`.
- **Failure handling**: On exception, `error_code_from_exception(exc)` maps to `ErrorCode`; `retry_class_for_error(code, contract)` decides retry policy.
- **Workers**: Use `idempotency_key(...)` when enqueueing or processing a step so duplicates are skipped.

## Adding a new action

1. Implement `BaseAction` in `apps/backend/actions/<name>.py`.
2. Register in `REGISTRY` in `registry.py`.
3. Add an `ActionContract` to `DEFAULT_CONTRACTS` in `contracts.py` with `capability_id`, `input_schema`, and `default_retry_class`.
