/**
 * Backend API client.
 * Uses normalized base URL (no trailing slash). Workflow calls retry /api/v1/* if /workflows/* returns 404.
 */
function _apiRoot() {
  return String(typeof BACKEND_URL !== "undefined" ? BACKEND_URL : "").replace(/\/+$/, "");
}

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

async function _errMessage(res) {
  const t = await res.text();
  try {
    const j = JSON.parse(t);
    if (j && j.detail != null) {
      return typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    }
    return t || res.statusText || String(res.status);
  } catch (e) {
    return t || res.statusText || String(res.status);
  }
}

/** POST: try primary path, then /api/v1 alias on 404. */
async function _postWorkflow(primaryPath, altPath, bodyObj) {
  const base = _apiRoot();
  const init = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bodyObj),
  };
  let res = await fetch(base + primaryPath, init);
  if (res.status === 404) {
    res = await fetch(base + altPath, init);
  }
  if (!res.ok) {
    const msg = await _errMessage(res);
    if (res.status === 404) {
      throw new Error(
        "Workflow API not found (404). The server is running old code or a proxy is blocking routes. " +
          "On EC2: cd ~/all-doing-bot && git pull origin main && source venv/bin/activate && " +
          "pip install -r apps/backend/requirements.txt && sudo systemctl restart alldoing — " +
          "then hard-refresh this page. Raw: " +
          msg
      );
    }
    throw new Error(msg);
  }
  return res.json();
}

/** GET with session query: try primary, then alt on 404. */
async function _getWorkflowList(primaryPath, altPath, limit) {
  const base = _apiRoot();
  const n = limit || 50;
  const q = "?limit=" + encodeURIComponent(n);
  const u1 = _withSession(base + primaryPath + q);
  let res = await fetch(u1);
  if (res.status === 404) {
    const u2 = _withSession(base + altPath + q);
    res = await fetch(u2);
  }
  if (!res.ok) {
    const msg = await _errMessage(res);
    if (res.status === 404) {
      throw new Error(
        "Workflow list not found (404). Update backend on EC2 (git pull, pip install, restart alldoing). " + msg
      );
    }
    throw new Error(msg);
  }
  return res.json();
}

const API = {
  async health() {
    const res = await fetch(_apiRoot() + "/health");
    if (!res.ok) throw new Error(await _errMessage(res));
    return res.json();
  },

  async chat(query) {
    const res = await fetch(_withSession(`${_apiRoot()}/chat?q=${encodeURIComponent(query)}`));
    if (!res.ok) throw new Error(await _errMessage(res));
    return res.json();
  },

  async clearData() {
    const res = await fetch(_apiRoot() + "/admin/clear-data", { method: "POST" });
    if (!res.ok) throw new Error(await _errMessage(res));
    return res.json();
  },

  async submitQuery(query) {
    const res = await fetch(_withSession(`${_apiRoot()}/query?q=${encodeURIComponent(query)}`));
    if (!res.ok) throw new Error(await _errMessage(res));
    return res.json();
  },

  async getStatus(taskId) {
    const res = await fetch(_apiRoot() + "/status/" + encodeURIComponent(taskId));
    if (!res.ok) throw new Error(await _errMessage(res));
    return res.json();
  },

  async listCohorts() {
    const res = await fetch(_apiRoot() + "/cohorts");
    if (!res.ok) throw new Error(await _errMessage(res));
    return res.json();
  },

  async getCohortEntries(name) {
    const res = await fetch(_apiRoot() + "/cohort/" + encodeURIComponent(name));
    if (!res.ok) throw new Error(await _errMessage(res));
    return res.json();
  },

  async addTask(text) {
    return _postWorkflow("/workflows/task", "/api/v1/workflow/task", {
      text,
      session_key: _sessionKey(),
    });
  },

  async addNote(text) {
    return _postWorkflow("/workflows/note", "/api/v1/workflow/note", {
      text,
      session_key: _sessionKey(),
    });
  },

  async listTasks(limit) {
    return _getWorkflowList("/workflows/tasks", "/api/v1/workflow/tasks", limit);
  },

  async listNotes(limit) {
    return _getWorkflowList("/workflows/notes", "/api/v1/workflow/notes", limit);
  },
};
