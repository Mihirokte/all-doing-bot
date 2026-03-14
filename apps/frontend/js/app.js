/** ALL-DOING Intelligence Terminal — chat-style UI, smart routing by length */

const CHAT_THRESHOLD = 100; // under this many chars: /chat (instant). else: /query (pipeline)
let queryCount = 0;
let pollTimer = null;

// Short query is "search-like" (mirrors backend) → show deep retrieval status
function looksLikeSearch(q) {
  const lower = (q || "").trim().toLowerCase();
  if (lower.length < 4) return false;
  const triggers = ["find", "search", "look up", "lookup", "get me", "fetch", "latest", "recent", "today", "this week", "top", "best", "trending", "what are the", "news about", "updates on", "launches", "release", "projects", "github"];
  return triggers.some(t => lower.includes(t));
}

// ── Boot ─────────────────────────────────────────────────
window.appBoot = function () {
  initClock();
  initQuickTags();
  initQueryBox();
  initProfile();
  initArchives();
  initSignOut();
  loadCohorts();
  checkBackend();
  document.getElementById("boot-ts").textContent = nowTs();
};

// ── Clock ─────────────────────────────────────────────────
function initClock() {
  const el = document.getElementById("sys-time");
  function tick() {
    el.textContent = new Date().toISOString().replace("T", " ").slice(0, 19) + " UTC";
  }
  tick();
  setInterval(tick, 1000);
}

// ── Quick-tag shortcuts ───────────────────────────────────
function initQuickTags() {
  document.querySelectorAll(".ex-tag").forEach(tag => {
    tag.addEventListener("click", () => {
      const input = document.getElementById("main-query");
      input.value = tag.dataset.q;
      input.focus();
    });
  });
}

// ── Query box: auto-clear on submit, smart routing ──────────
function initQueryBox() {
  const input = document.getElementById("main-query");
  const execBtn = document.getElementById("exec-btn");
  execBtn.addEventListener("click", () => submitQuery());
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") submitQuery();
  });
}

async function submitQuery() {
  const input = document.getElementById("main-query");
  const execBtn = document.getElementById("exec-btn");
  const q = input.value.trim();
  if (!q) return;

  // Auto-clear input immediately after submit
  input.value = "";
  execBtn.disabled = true;
  input.disabled = true;

  appendMsg("user", q);

  if (q.length < CHAT_THRESHOLD) {
    // Short path: /chat — deep retrieval when search-like, else LLM
    setTaskStatus("RUNNING", q);
    if (looksLikeSearch(q)) setDeepRetrievalStatus(true);
    showTaskBadge(true);
    try {
      const data = await API.chat(q);
      const responseText = (data.response || "").trim() || "No response.";
      appendMsg("assistant", responseText, false, null, true);
      setTaskStatus("COMPLETED", q);
    } catch (e) {
      appendMsg("assistant", "Error: " + (e.message || e), true);
      setTaskStatus("IDLE", "");
    }
    if (looksLikeSearch(q)) setDeepRetrievalStatus(false);
    showTaskBadge(false);
    execBtn.disabled = false;
    input.disabled = false;
    return;
  }

  // Long path: /query — pipeline, cohort, poll
  setTaskStatus("RUNNING", q);
  showProgressBar(true);
  showTaskBadge(true);
  try {
    const { task_id } = await API.submitQuery(q);
    document.getElementById("task-id-display").textContent = "TASK ID: " + task_id;
    startPoll(task_id);
  } catch (e) {
    appendMsg("result", "Submit failed: " + (e.message || e), true);
    resetTaskUI();
    execBtn.disabled = false;
    input.disabled = false;
  }
}

function startPoll(taskId) {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const d = await API.getStatus(taskId);
      const s = d.status;

      if (s === "completed") {
        clearInterval(pollTimer);
        pollTimer = null;
        queryCount++;
        document.getElementById("metric-queries").textContent = queryCount;
        setTaskStatus("COMPLETED", d.query || "");
        showProgressBar(false);
        showTaskBadge(false);
        appendMsg("result", formatResult(d.result), false, d.result);
        loadCohorts();
        resetInput();
      } else if (s === "failed") {
        clearInterval(pollTimer);
        pollTimer = null;
        setTaskStatus("FAILED", d.query || "");
        showProgressBar(false);
        showTaskBadge(false);
        const err = (d.result && d.result.error) ? d.result.error : "unknown error";
        appendMsg("result", "Task failed: " + err, true);
        resetInput();
      }
    } catch (e) {
      appendMsg("result", "Poll error: " + (e.message || e), true);
    }
  }, 3000);
}

function formatResult(result) {
  if (!result) return "No result.";
  if (result.error) return result.error;
  const n = result.entries_added != null ? result.entries_added : 0;
  const name = result.cohort_name || "cohort";
  let text = "Found " + n + " entries in cohort `" + name + "`. " + (result.message || "");
  const steps = result.raw && result.raw.steps;
  if (steps && steps.length) {
    const parts = steps.map(st => (st.action || "?") + (st.entry_count != null ? " (" + st.entry_count + ")" : ""));
    text += " Steps: " + parts.join(", ");
  }
  return text;
}

function resetInput() {
  document.getElementById("exec-btn").disabled = false;
  document.getElementById("main-query").disabled = false;
}

// ── Chat message feed ─────────────────────────────────────
function appendMsg(role, body, isError, resultPayload, useHtml) {
  const log = document.getElementById("feed-log");
  const msg = document.createElement("div");
  msg.className = "msg msg-" + role + (isError ? " msg-error" : "");
  const ts = nowTs();
  let inner = '<span class="msg-ts">' + ts + '</span>';
  if (role === "result" && resultPayload && (resultPayload.raw || resultPayload.message)) {
    inner += '<div class="msg-body">' + (useHtml ? formatChatBody(body) : escHtml(body)) + '</div>';
    if (resultPayload.raw && resultPayload.raw.steps) {
      inner += '<details class="msg-details"><summary>Details</summary><pre>' + escHtml(JSON.stringify(resultPayload, null, 2)) + '</pre></details>';
    }
  } else {
    inner += '<div class="msg-body">' + (useHtml ? formatChatBody(body) : escHtml(body)) + '</div>';
  }
  msg.innerHTML = inner;
  log.appendChild(msg);
  log.scrollTop = log.scrollHeight;
}

// Evidence-first chat: markdown links -> clickable; confidence -> badge
function formatChatBody(text) {
  if (!text) return "";
  const escaped = escHtml(text);
  const withLinks = escaped.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, (_, label, url) =>
    '<a href="' + escAttr(url) + '" target="_blank" rel="noopener" class="msg-evidence-link">' + label + '</a>'
  );
  const withConfidence = withLinks.replace(/\*Confidence: (high|medium|low)\*/gi, (_, level) =>
    '<span class="msg-confidence msg-confidence-' + level.toLowerCase() + '">Confidence: ' + escHtml(level) + '</span>'
  );
  return withConfidence.replace(/\n/g, "<br>");
}

function setDeepRetrievalStatus(active) {
  const el = document.getElementById("deep-retrieval-status");
  if (!el) return;
  el.classList.toggle("hidden", !active);
}

function nowTs() {
  return new Date().toISOString().slice(11, 19);
}

document.getElementById("clear-log").addEventListener("click", () => {
  const log = document.getElementById("feed-log");
  const boot = document.getElementById("boot-msg");
  log.innerHTML = "";
  if (boot) {
    log.appendChild(boot);
    const tsEl = boot.querySelector("#boot-ts");
    if (tsEl) tsEl.textContent = nowTs();
  } else {
    const sys = document.createElement("div");
    sys.className = "msg msg-system";
    sys.id = "boot-msg";
    sys.innerHTML = '<span class="msg-ts" id="boot-ts">' + nowTs() + '</span><span class="msg-body">Chat cleared.</span>';
    log.appendChild(sys);
  }
  log.scrollTop = log.scrollHeight;
});

// ── Task status card ──────────────────────────────────────
function setTaskStatus(state, query) {
  const el = document.getElementById("task-status");
  el.textContent = state;
  el.className = "task-status " + state.toLowerCase();
  const qEl = document.getElementById("task-query-display");
  qEl.textContent = query ? "> " + query : "";
}

function showProgressBar(show) {
  document.getElementById("progress-wrap").classList.toggle("hidden", !show);
}

function showTaskBadge(show) {
  document.getElementById("task-badge").classList.toggle("hidden", !show);
}

function resetTaskUI() {
  setTaskStatus("IDLE", "");
  showProgressBar(false);
  showTaskBadge(false);
  document.getElementById("task-id-display").textContent = "";
}

// ── Cohorts sidebar ───────────────────────────────────────
async function loadCohorts() {
  const list = document.getElementById("cohorts-list");
  const count = document.getElementById("cohort-count");
  try {
    const cohorts = await API.listCohorts();
    count.textContent = cohorts.length;
    if (!cohorts.length) {
      list.innerHTML = '<div class="cohorts-empty">No archives yet.</div>';
      return;
    }
    list.innerHTML = cohorts.map(c =>
      '<div class="cohort-item" data-name="' + escAttr(c.cohort_name) + '">' +
        '<span class="c-name">' + escHtml(c.cohort_name) + '</span>' +
        '<span class="c-count">' + (c.entry_count || 0) + '</span>' +
      '</div>'
    ).join("");
    list.querySelectorAll(".cohort-item").forEach(item => {
      item.addEventListener("click", () => openArchives(item.dataset.name));
    });
  } catch (e) {
    list.innerHTML = '<div class="cohorts-empty" style="color:var(--red)">LOAD FAILED</div>';
  }
}

// ── Archives overlay ──────────────────────────────────────
function initArchives() {
  document.getElementById("archives-toggle").addEventListener("click", () => openArchives());
  document.getElementById("close-archives").addEventListener("click", () =>
    document.getElementById("archives-overlay").classList.add("hidden")
  );
}

// ── Profile overlay + data reset ──────────────────────────
function initProfile() {
  const openBtn = document.getElementById("profile-toggle");
  const closeBtn = document.getElementById("close-profile");
  const overlay = document.getElementById("profile-overlay");
  const clearBtn = document.getElementById("clear-all-data-btn");
  const statusEl = document.getElementById("profile-status");

  openBtn.addEventListener("click", () => {
    statusEl.textContent = "";
    overlay.classList.remove("hidden");
  });
  closeBtn.addEventListener("click", () => overlay.classList.add("hidden"));

  clearBtn.addEventListener("click", async () => {
    const ok = window.confirm("This will delete all past sessions and cohort data. Continue?");
    if (!ok) return;
    clearBtn.disabled = true;
    statusEl.textContent = "Clearing data...";
    try {
      const r = await API.clearData();
      statusEl.textContent = "Done. Deleted cohorts: " + (r.deleted_cohorts || 0) + ", cleared sessions: " + (r.cleared_tasks || 0) + ".";
      queryCount = 0;
      document.getElementById("metric-queries").textContent = "0";
      resetTaskUI();
      document.getElementById("feed-log").innerHTML =
        '<div class="msg msg-system" id="boot-msg"><span class="msg-ts" id="boot-ts">' + nowTs() + '</span><span class="msg-body">All history cleared. Ready for a fresh start.</span></div>';
      await loadCohorts();
    } catch (e) {
      statusEl.textContent = "Failed: " + (e.message || e);
    } finally {
      clearBtn.disabled = false;
    }
  });
}

async function openArchives(selectedCohort) {
  const overlay = document.getElementById("archives-overlay");
  overlay.classList.remove("hidden");
  const cohortsEl = document.getElementById("archives-cohorts");
  const entriesEl = document.getElementById("archives-entries");
  cohortsEl.innerHTML = '<div style="color:var(--muted);font-size:12px">Loading…</div>';
  entriesEl.innerHTML = '<div class="entries-placeholder">SELECT A COHORT TO VIEW ENTRIES</div>';
  try {
    const cohorts = await API.listCohorts();
    if (!cohorts.length) {
      cohortsEl.innerHTML = '<div class="cohorts-empty">No archives.</div>';
      return;
    }
    cohortsEl.innerHTML = cohorts.map(c =>
      '<div class="cohort-item' + (c.cohort_name === selectedCohort ? ' selected' : '') +
      '" data-name="' + escAttr(c.cohort_name) + '">' +
        '<span class="c-name">' + escHtml(c.cohort_name) + '</span>' +
        '<span class="c-count">' + (c.entry_count || 0) + '</span>' +
      '</div>'
    ).join("");
    cohortsEl.querySelectorAll(".cohort-item").forEach(item => {
      item.addEventListener("click", () => loadEntries(item.dataset.name, entriesEl));
    });
    if (selectedCohort) loadEntries(selectedCohort, entriesEl);
  } catch (e) {
    cohortsEl.innerHTML = '<div class="cohorts-empty" style="color:var(--red)">LOAD FAILED</div>';
  }
}

async function loadEntries(name, container) {
  container.innerHTML = '<div style="color:var(--muted);padding:16px;font-size:12px">LOADING ENTRIES…</div>';
  try {
    const entries = await API.getCohortEntries(name);
    if (!entries.length) {
      container.innerHTML = '<div class="entries-placeholder">NO ENTRIES IN THIS COHORT</div>';
      return;
    }
    container.innerHTML = entries.map(e =>
      '<div class="entry-row">' +
        '<div class="entry-id">ID: ' + escHtml(e.entry_id || "") + '</div>' +
        '<div class="entry-content">' + escHtml((e.content || "").slice(0, 300)) + '</div>' +
        '<div class="entry-source">SOURCE: ' + escHtml(e.source || "unknown") + '</div>' +
      '</div>'
    ).join("");
  } catch (e) {
    container.innerHTML = '<div class="entries-placeholder" style="color:var(--red)">LOAD FAILED</div>';
  }
}

// ── Backend health check ──────────────────────────────────
async function checkBackend() {
  const el = document.getElementById("metric-backend");
  try {
    await API.health();
    el.textContent = "CONNECTED";
    el.classList.add("online");
  } catch (e) {
    el.textContent = "OFFLINE";
    el.style.color = "var(--red)";
    document.getElementById("sys-status").textContent = "DEGRADED";
    document.getElementById("sys-status").style.color = "var(--amber)";
  }
}

// ── Sign out ──────────────────────────────────────────────
function initSignOut() {
  document.getElementById("signout-btn").addEventListener("click", () => {
    if (window.clearAllDoingLoginCache) window.clearAllDoingLoginCache();
  });
}

// ── Helpers ───────────────────────────────────────────────
function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

function escAttr(s) {
  return String(s).replace(/"/g, "&quot;");
}

window.appRefreshCohorts = loadCohorts;
