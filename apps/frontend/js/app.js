/** ALL-DOING Intelligence Terminal — main application logic */

let queryCount = 0;
let pollTimer  = null;

// ── Boot ─────────────────────────────────────────────────
window.appBoot = function () {
  initClock();
  initQuickTags();
  initQueryBox();
  initArchives();
  initSignOut();
  loadCohorts();
  checkBackend();
  logEntry("system", "TERMINAL ONLINE. OPERATOR ACCESS GRANTED.");
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

// ── Query box ─────────────────────────────────────────────
function initQueryBox() {
  const input   = document.getElementById("main-query");
  const execBtn = document.getElementById("exec-btn");

  execBtn.addEventListener("click", () => submitQuery());
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") submitQuery();
  });
}

async function submitQuery() {
  const input   = document.getElementById("main-query");
  const execBtn = document.getElementById("exec-btn");
  const q = input.value.trim();
  if (!q) return;

  execBtn.disabled = true;
  input.disabled   = true;
  setTaskStatus("RUNNING", q);
  showProgressBar(true);
  showTaskBadge(true);
  closeResult();

  logEntry("submit", "EXECUTING: " + q);

  try {
    const { task_id } = await API.submitQuery(q);
    logEntry("info", "TASK ACCEPTED · ID: " + task_id.slice(0, 8) + "...");
    document.getElementById("task-id-display").textContent =
      "TASK ID: " + task_id;
    startPoll(task_id);
  } catch (e) {
    logEntry("error", "SUBMIT FAILED: " + (e.message || e));
    resetTaskUI();
    execBtn.disabled = false;
    input.disabled   = false;
  }
}

function startPoll(taskId) {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const d = await API.getStatus(taskId);
      const s = d.status;

      if (s === "completed") {
        clearInterval(pollTimer); pollTimer = null;
        queryCount++;
        document.getElementById("metric-queries").textContent = queryCount;
        setTaskStatus("COMPLETED", d.query || "");
        showProgressBar(false);
        showTaskBadge(false);
        logEntry("success", "TASK COMPLETE · " + taskId.slice(0, 8));
        showResult(d.result);
        loadCohorts();
        resetInput();
      } else if (s === "failed") {
        clearInterval(pollTimer); pollTimer = null;
        setTaskStatus("FAILED", d.query || "");
        showProgressBar(false);
        showTaskBadge(false);
        logEntry("error", "TASK FAILED · " +
          ((d.result && d.result.error) ? d.result.error : "unknown error"));
        resetInput();
      } else {
        logEntry("info", "STATUS: " + s.toUpperCase());
      }
    } catch (e) {
      logEntry("error", "POLL ERROR: " + (e.message || e));
    }
  }, 3000);
}

function resetInput() {
  const execBtn = document.getElementById("exec-btn");
  const input   = document.getElementById("main-query");
  execBtn.disabled = false;
  input.disabled   = false;
}

// ── Task status card ──────────────────────────────────────
function setTaskStatus(state, query) {
  const el = document.getElementById("task-status");
  el.textContent = state;
  el.className = "task-status " + state.toLowerCase();
  const qEl = document.getElementById("task-query-display");
  qEl.textContent = query ? "> " + query : "";
}

function showProgressBar(show) {
  const wrap = document.getElementById("progress-wrap");
  wrap.classList.toggle("hidden", !show);
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

// ── Log feed ──────────────────────────────────────────────
function logEntry(type, msg) {
  const log = document.getElementById("feed-log");
  const row = document.createElement("div");
  row.className = "log-entry " + type;
  row.innerHTML =
    '<span class="log-ts">' + nowTs() + '</span>' +
    '<span class="log-msg">' + escHtml(msg) + '</span>';
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
}

function nowTs() {
  return new Date().toISOString().slice(11, 19);
}

document.getElementById("clear-log").addEventListener("click", () => {
  const log = document.getElementById("feed-log");
  log.innerHTML = "";
  logEntry("system", "LOG CLEARED.");
});

// ── Result panel ──────────────────────────────────────────
function showResult(result) {
  const panel   = document.getElementById("result-panel");
  const content = document.getElementById("result-content");

  if (!result) {
    content.textContent = "No result data.";
  } else if (typeof result === "string") {
    content.textContent = result;
  } else {
    content.textContent = JSON.stringify(result, null, 2);
  }
  panel.classList.remove("hidden");
}

function closeResult() {
  document.getElementById("result-panel").classList.add("hidden");
}

document.getElementById("close-result").addEventListener("click", closeResult);

// ── Cohorts sidebar ───────────────────────────────────────
async function loadCohorts() {
  const list  = document.getElementById("cohorts-list");
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
    logEntry("success", "BACKEND CONNECTED: " + (window.BACKEND_URL || ""));
  } catch (e) {
    el.textContent = "OFFLINE";
    el.style.color = "var(--red)";
    logEntry("error", "BACKEND UNREACHABLE: " + (e.message || e));
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

// Expose for outside callers
window.appRefreshCohorts = loadCohorts;
