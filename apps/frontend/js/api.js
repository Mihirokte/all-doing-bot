/**
 * Backend API client.
 * Endpoints (FastAPI main.py):
 *   GET /health           -> { status: "ok" }
 *   GET /chat?q=...       -> { response: "..." }  (short queries, no cohort)
 *   GET /query?q=...      -> { task_id, status: "accepted" }
 *   GET /status/{task_id} -> { task_id, status, query?, result? }
 *   POST /admin/clear-data -> { status, deleted_cohorts, cleared_tasks }
 *   GET /cohorts          -> [{ cohort_name, cohort_description, action_type, sheet_name, entry_count, created_at, last_run }]
 *   GET /cohort/{name}    -> [{ entry_id, content, source, metadata, created_at }]
 *   POST /workflows/task  -> { ok, cohort_name, entry_id, message }  (JSON body: text, session_key)
 *   POST /workflows/note  -> same
 *   GET /workflows/tasks?session_key=&limit=
 *   GET /workflows/notes?session_key=&limit=
 */
function _sessionKey() {
  if (typeof window !== "undefined" && typeof window.getSessionKey === "function") {
    return window.getSessionKey();
  }
  return "default";
}

function _withSession(url) {
  const sep = url.includes("?") ? "&" : "?";
  return url + sep + "session_key=" + encodeURIComponent(_sessionKey());
}

const API = {
  async health() {
    const res = await fetch(`${BACKEND_URL}/health`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async chat(query) {
    const res = await fetch(_withSession(`${BACKEND_URL}/chat?q=${encodeURIComponent(query)}`));
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async clearData() {
    const res = await fetch(`${BACKEND_URL}/admin/clear-data`, { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async submitQuery(query) {
    const res = await fetch(_withSession(`${BACKEND_URL}/query?q=${encodeURIComponent(query)}`));
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

  async addTask(text) {
    const res = await fetch(`${BACKEND_URL}/workflows/task`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, session_key: _sessionKey() }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async addNote(text) {
    const res = await fetch(`${BACKEND_URL}/workflows/note`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, session_key: _sessionKey() }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async listTasks(limit) {
    const n = limit || 50;
    const res = await fetch(_withSession(`${BACKEND_URL}/workflows/tasks?limit=${n}`));
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async listNotes(limit) {
    const n = limit || 50;
    const res = await fetch(_withSession(`${BACKEND_URL}/workflows/notes?limit=${n}`));
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
