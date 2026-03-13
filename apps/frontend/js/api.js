/**
 * Backend API client.
 * Endpoints (FastAPI main.py):
 *   GET /health           -> { status: "ok" }
 *   GET /query?q=...      -> { task_id, status: "accepted" }
 *   GET /status/{task_id} -> { task_id, status, query?, result? }
 *   GET /cohorts          -> [{ cohort_name, cohort_description, action_type, sheet_name, entry_count, created_at, last_run }]
 *   GET /cohort/{name}    -> [{ entry_id, content, source, metadata, created_at }]
 */
const API = {
  async health() {
    const res = await fetch(`${BACKEND_URL}/health`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async submitQuery(query) {
    const res = await fetch(`${BACKEND_URL}/query?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getStatus(taskId) {
    const res = await fetch(`${BACKEND_URL}/status/${taskId}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async listCohorts() {
    const res = await fetch(`${BACKEND_URL}/cohorts`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getCohortEntries(name) {
    const res = await fetch(`${BACKEND_URL}/cohort/${encodeURIComponent(name)}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
