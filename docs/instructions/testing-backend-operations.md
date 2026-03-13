# Testing backend operations

Ways to test the backend API (locally or on EC2).

## Base URL

- **Local:** `http://localhost:8000`
- **EC2:** `http://54.165.94.30:8000` (or your instance’s public IP)

Set `BASE=http://localhost:8000` or `BASE=http://54.165.94.30:8000` and use `$BASE` in the examples below.

---

## 1. Health check

```bash
curl -s "$BASE/health"
# Expected: {"status":"ok"}
```

---

## 2. Submit a query (full pipeline)

Submit a natural-language query. The backend creates a task and runs the pipeline in the background (parse → plan → execute → store).

```bash
curl -s "$BASE/query?q=Create%20a%20cohort%20called%20test-cohort%20and%20fetch%20news%20about%20AI"
# Expected: {"task_id":"<uuid>","status":"accepted"}
```

Save the `task_id` from the response for the next step.

---

## 3. Poll task status

Check status and result for a task (repeat until `status` is `completed` or `failed`).

```bash
TASK_ID="<paste-task-id-here>"
curl -s "$BASE/status/$TASK_ID"
# Example when done: {"task_id":"...","status":"completed","query":"...","result":{...},"created_at":"...","updated_at":"..."}
```

---

## 4. List cohorts

List all cohorts from the catalogue (in-memory or Google Sheets, depending on config).

```bash
curl -s "$BASE/cohorts"
# Array of cohort objects: cohort_name, cohort_description, action_type, sheet_name, entry_count, etc.
```

---

## 5. Get cohort entries

Get entries for a specific cohort.

```bash
curl -s "$BASE/cohort/test-cohort"
# Array of entries: entry_id, content, source, metadata, created_at
```

Use a cohort name that exists (from `/cohorts`). If the cohort doesn’t exist you get 404.

---

## One-liner flow (local or EC2)

```bash
BASE="http://localhost:8000"   # or http://54.165.94.30:8000

# 1. Health
curl -s "$BASE/health"

# 2. Submit query and capture task_id
RESP=$(curl -s "$BASE/query?q=Create%20cohort%20demo%20and%20fetch%20AI%20news")
echo "$RESP"
TASK_ID=$(echo "$RESP" | python -c "import sys,json; print(json.load(sys.stdin).get('task_id',''))")

# 3. Poll until done (simplified: poll a few times)
for i in 1 2 3 4 5 6 7 8 9 10; do
  sleep 2
  STATUS=$(curl -s "$BASE/status/$TASK_ID" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))")
  echo "Poll $i: status=$STATUS"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
done

# 4. List cohorts and show one
curl -s "$BASE/cohorts"
curl -s "$BASE/cohort/demo"
```

---

## Task result diagnostics

When a task completes, `result.raw` may contain per-step diagnostics:

```json
{ "steps": [ { "action": "search_web", "entry_count": 5 }, { "action": "transform", "entry_count": 2 } ] }
```

Use this to verify which actions ran and how many entries each produced.

---

## Unit tests

From the repo root:

```bash
python -m pytest tests -q
```

Covers pipeline, executor guardrails, multi-step diagnostics, LLM (mock), actions (including web_search/web_fetch), config, and Google persistence (mocked where needed).
