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
  try {
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
  } catch (e) {
    // Body already consumed or unreadable
    return res.statusText || String(res.status);
  }
}

/**
 * Build a structured error object with message, status, and timeout flag.
 */
function _apiError(message, status, isTimeout) {
  const err = new Error(message);
  err.status = status || 0;
  err.isTimeout = !!isTimeout;
  return err;
}

/**
 * Wrap a fetch call with a timeout via AbortController.
 * @param {string} url
 * @param {RequestInit} [init]
 * @param {number} [timeoutMs] - timeout in milliseconds
 * @param {AbortSignal} [externalSignal] - optional caller-provided signal
 * @returns {Promise<Response>}
 */
async function _fetchWithTimeout(url, init, timeoutMs, externalSignal) {
  const controller = new AbortController();
  const signals = [controller.signal];
  if (externalSignal) signals.push(externalSignal);

  // If the external signal is already aborted, throw immediately
  if (externalSignal && externalSignal.aborted) {
    throw _apiError("Request aborted", 0, false);
  }

  // Combine signals: abort our controller if the external signal fires
  let onExternalAbort;
  if (externalSignal) {
    onExternalAbort = () => controller.abort();
    externalSignal.addEventListener("abort", onExternalAbort, { once: true });
  }

  const timer = timeoutMs
    ? setTimeout(() => controller.abort(), timeoutMs)
    : null;

  try {
    const res = await fetch(url, { ...init, signal: controller.signal });
    return res;
  } catch (e) {
    if (e.name === "AbortError") {
      // Distinguish timeout from external abort
      if (externalSignal && externalSignal.aborted) {
        throw _apiError("Request aborted", 0, false);
      }
      throw _apiError("Request timed out after " + timeoutMs + "ms", 0, true);
    }
    throw e;
  } finally {
    if (timer) clearTimeout(timer);
    if (externalSignal && onExternalAbort) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }
}

/** Default timeouts */
const _TIMEOUT_DEFAULT = 30000;
const _TIMEOUT_QUERY = 60000;

/** POST: try primary path, then /api/v1 alias on 404. */
async function _postWorkflow(primaryPath, altPath, bodyObj, signal) {
  const base = _apiRoot();
  const init = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bodyObj),
  };
  let res = await _fetchWithTimeout(base + primaryPath, init, _TIMEOUT_DEFAULT, signal);
  if (res.status === 404) {
    res = await _fetchWithTimeout(base + altPath, init, _TIMEOUT_DEFAULT, signal);
  }
  if (!res.ok) {
    const msg = await _errMessage(res);
    if (res.status === 404) {
      throw _apiError(
        "Workflow API not found (404). The server is running old code or a proxy is blocking routes. " +
          "On EC2: cd ~/all-doing-bot && git pull origin main && source venv/bin/activate && " +
          "pip install -r apps/backend/requirements.txt && sudo systemctl restart alldoing — " +
          "then hard-refresh this page. Raw: " +
          msg,
        404,
        false
      );
    }
    throw _apiError(msg, res.status, false);
  }
  return res.json();
}

/** GET with session query: try primary, then alt on 404. */
async function _getWorkflowList(primaryPath, altPath, limit, signal) {
  const base = _apiRoot();
  const n = limit || 50;
  const q = "?limit=" + encodeURIComponent(n);
  const u1 = _withSession(base + primaryPath + q);
  let res = await _fetchWithTimeout(u1, undefined, _TIMEOUT_DEFAULT, signal);
  if (res.status === 404) {
    const u2 = _withSession(base + altPath + q);
    res = await _fetchWithTimeout(u2, undefined, _TIMEOUT_DEFAULT, signal);
  }
  if (!res.ok) {
    const msg = await _errMessage(res);
    if (res.status === 404) {
      throw _apiError(
        "Workflow list not found (404). Update backend on EC2 (git pull, pip install, restart alldoing). " + msg,
        404,
        false
      );
    }
    throw _apiError(msg, res.status, false);
  }
  return res.json();
}

const API = {
  /**
   * GET /health → { status, api: { version, chat, pipeline, workflows, task_store } }
   * task_store is "redis" or "memory" (shared task state when redis).
   */
  async health(signal) {
    const res = await _fetchWithTimeout(_apiRoot() + "/health", undefined, _TIMEOUT_DEFAULT, signal);
    if (!res.ok) throw _apiError(await _errMessage(res), res.status, false);
    return res.json();
  },

  async chat(query, signal) {
    const res = await _fetchWithTimeout(
      _withSession(`${_apiRoot()}/chat?q=${encodeURIComponent(query)}`),
      undefined,
      _TIMEOUT_QUERY,
      signal
    );
    if (!res.ok) throw _apiError(await _errMessage(res), res.status, false);
    return res.json();
  },

  async clearData(signal) {
    const res = await _fetchWithTimeout(
      _apiRoot() + "/admin/clear-data",
      { method: "POST" },
      _TIMEOUT_DEFAULT,
      signal
    );
    if (!res.ok) throw _apiError(await _errMessage(res), res.status, false);
    return res.json();
  },

  async submitQuery(query, signal) {
    const res = await _fetchWithTimeout(
      _withSession(`${_apiRoot()}/query?q=${encodeURIComponent(query)}`),
      undefined,
      _TIMEOUT_QUERY,
      signal
    );
    if (!res.ok) throw _apiError(await _errMessage(res), res.status, false);
    return res.json();
  },

  async getStatus(taskId, signal) {
    const res = await _fetchWithTimeout(
      _apiRoot() + "/status/" + encodeURIComponent(taskId),
      undefined,
      _TIMEOUT_DEFAULT,
      signal
    );
    if (!res.ok) throw _apiError(await _errMessage(res), res.status, false);
    return res.json();
  },

  async listCohorts(signal) {
    const res = await _fetchWithTimeout(_apiRoot() + "/cohorts", undefined, _TIMEOUT_DEFAULT, signal);
    if (!res.ok) throw _apiError(await _errMessage(res), res.status, false);
    return res.json();
  },

  async getCohortEntries(name, signal) {
    const res = await _fetchWithTimeout(
      _apiRoot() + "/cohort/" + encodeURIComponent(name),
      undefined,
      _TIMEOUT_DEFAULT,
      signal
    );
    if (!res.ok) throw _apiError(await _errMessage(res), res.status, false);
    return res.json();
  },

  async addTask(text, signal) {
    return _postWorkflow("/workflows/task", "/api/v1/workflow/task", {
      text,
      session_key: _sessionKey(),
    }, signal);
  },

  async addNote(text, signal) {
    return _postWorkflow("/workflows/note", "/api/v1/workflow/note", {
      text,
      session_key: _sessionKey(),
    }, signal);
  },

  async listTasks(limit, signal) {
    return _getWorkflowList("/workflows/tasks", "/api/v1/workflow/tasks", limit, signal);
  },

  async listNotes(limit, signal) {
    return _getWorkflowList("/workflows/notes", "/api/v1/workflow/notes", limit, signal);
  },
};
