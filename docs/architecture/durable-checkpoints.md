# Durable Checkpoints (Queue Runtime)

Queue-orchestrated runs persist checkpoint metadata so long-running tasks can be inspected, replayed, and recovered.

## What is persisted

- **Run metadata** (`alldoing:run_meta:{run_id}`):
  - query, step_count, parsed_json, plan_json, status
- **Step results** (`alldoing:step_result:{run_id}:{step_index}`):
  - action, entry_count, entries, error/error_code
- **Dead letters** (`alldoing:step_dead_letter`):
  - unrecoverable step outcomes after retry policy is exhausted

## Runtime behavior

- Executor dispatches step payloads to queue first.
- Worker consumes payloads and applies retry policy from action contracts.
- Executor polls step results and stores final output with:
  - `execution_mode`
  - `tool_path`
  - `dead_letters`

## Recovery

- With `REDIS_URL` configured, run metadata survives API restarts.
- `update_run_status()` marks `completed`, `completed_with_dead_letters`, or `failed`.
- Idempotency key and duplicate-skip events prevent double execution of the same run step.
