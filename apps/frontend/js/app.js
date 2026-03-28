/** ALL-DOING Intelligence Terminal — chat-style UI, smart routing by length */

const CHAT_THRESHOLD = 100; // under this many chars: /chat (instant). else: /query (pipeline)
const MAX_QUERY_LENGTH = 10000;
const MAX_POLL_COUNT = 60;
/** @type {"ask"|"task"|"note"} */
let workflowMode = "ask";
let queryCount = 0;
let thinkingMessageEl = null;
let thinkingShownAtMs = 0;
const MIN_THINKING_VISIBLE_MS = 900;

// ── Abort / poll state ───────────────────────────────────
/** @type {AbortController|null} */
let activeAbortController = null;
/** @type {boolean} */
let pollRunning = false;

// ── Interval tracking ────────────────────────────────────
/** @type {number|null} */
let clockIntervalId = null;

// Short query is "search-like" (mirrors backend) → show deep retrieval status
function looksLikeSearch(q) {
  const lower = (q || "").trim().toLowerCase();
  if (lower.length < 4) return false;
  const triggers = [
    "find", "search", "look up", "lookup", "get me", "fetch", "latest", "recent", "today", "this week",
    "top", "best", "trending", "what are the", "news about", "updates on", "launches", "release", "projects", "github",
    "review", "reviews", "movie", "movies", "film", "imdb", "rotten", "critic", "rating", "ratings", "box office",
    "sequel", "trailer", "tell me the", "are you sure", "sources",
  ];
  return triggers.some(t => lower.includes(t));
}

// ── Boot ─────────────────────────────────────────────────
window.appBoot = function () {
  initClock();
  initWorkflowModes();
  initQueryBox();
  initProfile();
  initArchives();
  initSignOut();
  loadCohorts();
  loadWorkflowPanels();
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
  if (clockIntervalId) clearInterval(clockIntervalId);
  clockIntervalId = setInterval(tick, 1000);
}

function stopClock() {
  if (clockIntervalId) {
    clearInterval(clockIntervalId);
    clockIntervalId = null;
  }
}

// ── Quick workflow: Ask AI | Add task | Note it ────────────
function initWorkflowModes() {
  document.querySelectorAll(".mode-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      workflowMode = /** @type {"ask"|"task"|"note"} */ (btn.dataset.mode || "ask");
      document.querySelectorAll(".mode-chip").forEach(b => b.classList.toggle("active", b === btn));
      const input = document.getElementById("main-query");
      if (workflowMode === "ask") {
        input.placeholder = "Ask anything, search, or request research…";
      } else if (workflowMode === "task") {
        input.placeholder = "Task title or description (saved without AI)…";
      } else {
        input.placeholder = "Note text (saved without AI)…";
      }
      input.focus();
    });
  });
  const ref = document.getElementById("refresh-workflows");
  if (ref) ref.addEventListener("click", () => loadWorkflowPanels());
}

async function loadWorkflowPanels() {
  try {
    const tasks = await API.listTasks(40);
    renderWorkflowList("tasks-list", tasks);
  } catch (e) {
    console.error("Failed to load tasks:", e);
    const el = document.getElementById("tasks-list");
    if (el) el.innerHTML = '<div class="workflow-empty" style="color:var(--red)">Failed to load tasks: ' + escHtml(e.message || String(e)) + '</div>';
  }
  try {
    const notes = await API.listNotes(40);
    renderWorkflowList("notes-list", notes);
  } catch (e) {
    console.error("Failed to load notes:", e);
    const el = document.getElementById("notes-list");
    if (el) el.innerHTML = '<div class="workflow-empty" style="color:var(--red)">Failed to load notes: ' + escHtml(e.message || String(e)) + '</div>';
  }
}

function renderWorkflowList(elementId, items) {
  const el = document.getElementById(elementId);
  if (!el) return;
  if (!items || !items.length) {
    el.innerHTML = '<div class="workflow-empty">No items yet.</div>';
    return;
  }
  el.innerHTML = items.map(t => {
    const ts = (t.created_at || "").replace("T", " ").slice(0, 19);
    const body = escHtml((t.content || "").slice(0, 220));
    return '<div class="workflow-row"><span class="wf-ts">' + escHtml(ts) + '</span><div class="wf-body">' + body + "</div></div>";
  }).join("");
}

// ── Abort helpers ─────────────────────────────────────────
function abortActiveRequest() {
  if (activeAbortController) {
    activeAbortController.abort();
    activeAbortController = null;
  }
}

function newAbortController() {
  abortActiveRequest();
  activeAbortController = new AbortController();
  return activeAbortController;
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

  // Prevent double-submission while processing
  if (execBtn.disabled) return;

  // Input validation: max query length
  if (q.length > MAX_QUERY_LENGTH) {
    appendMsg("assistant", "Error: Query is too long (" + q.length + " characters). Maximum allowed is " + MAX_QUERY_LENGTH + " characters.", true);
    return;
  }

  // Abort any in-flight request from a previous submission
  abortActiveRequest();
  const controller = newAbortController();
  const signal = controller.signal;

  // Auto-clear input immediately after submit
  input.value = "";
  execBtn.disabled = true;
  input.disabled = true;

  appendMsg("user", q);

  if (workflowMode === "task") {
    setTaskStatus("RUNNING", q);
    showTaskBadge(true);
    try {
      const r = await API.addTask(q, signal);
      const msg = (r && r.message) ? r.message : "Task saved.";
      appendMsg("assistant", r.ok ? msg : ("Error: " + (r.error || msg)), !r.ok);
      setTaskStatus(r.ok ? "COMPLETED" : "FAILED", q);
      await loadWorkflowPanels();
      await loadCohorts();
    } catch (e) {
      if (signal.aborted) return; // Superseded by new request
      appendMsg("assistant", "Error: " + (e.message || e), true);
      setTaskStatus("FAILED", q);
    }
    showTaskBadge(false);
    execBtn.disabled = false;
    input.disabled = false;
    return;
  }

  if (workflowMode === "note") {
    setTaskStatus("RUNNING", q);
    showTaskBadge(true);
    try {
      const r = await API.addNote(q, signal);
      const msg = (r && r.message) ? r.message : "Note saved.";
      appendMsg("assistant", r.ok ? msg : ("Error: " + (r.error || msg)), !r.ok);
      setTaskStatus(r.ok ? "COMPLETED" : "FAILED", q);
      await loadWorkflowPanels();
      await loadCohorts();
    } catch (e) {
      if (signal.aborted) return; // Superseded by new request
      appendMsg("assistant", "Error: " + (e.message || e), true);
      setTaskStatus("FAILED", q);
    }
    showTaskBadge(false);
    execBtn.disabled = false;
    input.disabled = false;
    return;
  }

  if (q.length < CHAT_THRESHOLD) {
    // Short path: /chat — deep retrieval when search-like, else LLM
    setTaskStatus("RUNNING", q);
    if (looksLikeSearch(q)) setDeepRetrievalStatus(true);
    showTaskBadge(true);
    showThinkingIndicator("Thinking");
    try {
      const data = await API.chat(q, signal);
      const responseText = (data.response || "").trim() || "No response.";
      await hideThinkingIndicator();
      appendMsg("assistant", responseText, false, null, true);
      setTaskStatus("COMPLETED", q);
    } catch (e) {
      await hideThinkingIndicator();
      if (signal.aborted) return; // Superseded by new request
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
  showThinkingIndicator("Researching");
  try {
    const { task_id } = await API.submitQuery(q, signal);
    document.getElementById("task-id-display").textContent = "TASK ID: " + task_id;
    startPoll(task_id, signal);
  } catch (e) {
    if (signal.aborted) return; // Superseded by new request
    appendMsg("result", "Submit failed: " + (e.message || e), true);
    resetTaskUI();
    execBtn.disabled = false;
    input.disabled = false;
  }
}

/**
 * Compute polling interval with backoff.
 * Start at 2s, increase to 4s after 10 polls, then 8s after 20 polls.
 */
function getPollInterval(pollCount) {
  if (pollCount >= 20) return 8000;
  if (pollCount >= 10) return 4000;
  return 2000;
}

/**
 * Async poll loop with AbortController support, backoff, max polls,
 * and consecutive failure tolerance.
 */
async function startPoll(taskId, signal) {
  // Only one poll loop at a time
  if (pollRunning) return;
  pollRunning = true;

  let pollCount = 0;
  let consecutiveFailures = 0;
  const MAX_CONSECUTIVE_FAILURES = 3;

  try {
    while (pollCount < MAX_POLL_COUNT) {
      // Check if aborted before sleeping
      if (signal && signal.aborted) {
        pollRunning = false;
        return;
      }

      // Wait with backoff
      const interval = getPollInterval(pollCount);
      await new Promise((resolve, reject) => {
        const timer = setTimeout(resolve, interval);
        if (signal) {
          const onAbort = () => {
            clearTimeout(timer);
            resolve(); // Resolve so we can check abort at the top of the loop
          };
          signal.addEventListener("abort", onAbort, { once: true });
        }
      });

      // Check again after sleep
      if (signal && signal.aborted) {
        pollRunning = false;
        return;
      }

      pollCount++;

      try {
        const d = await API.getStatus(taskId, signal);
        consecutiveFailures = 0; // reset on success
        const s = d.status;

        if (s === "completed") {
          await hideThinkingIndicator();
          queryCount++;
          document.getElementById("metric-queries").textContent = queryCount;
          setTaskStatus("COMPLETED", d.query || "");
          showProgressBar(false);
          showTaskBadge(false);
          appendMsg("result", formatResult(d.result), false, d.result);
          loadCohorts();
          loadWorkflowPanels();
          resetInput();
          pollRunning = false;
          return;
        } else if (s === "failed") {
          await hideThinkingIndicator();
          setTaskStatus("FAILED", d.query || "");
          showProgressBar(false);
          showTaskBadge(false);
          const err = (d.result && d.result.error) ? d.result.error : "unknown error";
          appendMsg("result", "Task failed: " + err, true);
          resetInput();
          pollRunning = false;
          return;
        }
        // else: still running, continue polling
      } catch (e) {
        // If aborted, stop silently
        if (signal && signal.aborted) {
          pollRunning = false;
          return;
        }

        consecutiveFailures++;
        console.warn("Poll error (attempt " + consecutiveFailures + "/" + MAX_CONSECUTIVE_FAILURES + "):", e.message || e);

        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
          await hideThinkingIndicator();
          appendMsg("result", "Polling stopped after " + MAX_CONSECUTIVE_FAILURES + " consecutive network errors: " + (e.message || e), true);
          resetTaskUI();
          resetInput();
          pollRunning = false;
          return;
        }
        // Transient error: continue polling
      }
    }

    // Reached max poll count
    await hideThinkingIndicator();
    appendMsg("result", "This is taking longer than expected. The task is still running in the background.", false);
    showProgressBar(false);
    showTaskBadge(false);
    setTaskStatus("IDLE", "");
    resetInput();
  } finally {
    pollRunning = false;
  }
}

function showThinkingIndicator(label) {
  clearThinkingIndicatorNow();
  const log = document.getElementById("feed-log");
  const msg = document.createElement("div");
  msg.className = "msg msg-assistant msg-thinking";
  msg.innerHTML =
    '<span class="msg-ts">' + nowTs() + '</span>' +
    '<div class="msg-body">' + escHtml(label || "Thinking") +
    '<span class="thinking-dots">' +
    '<span></span><span></span><span></span>' +
    '</span></div>';
  log.appendChild(msg);
  log.scrollTop = log.scrollHeight;
  thinkingMessageEl = msg;
  thinkingShownAtMs = Date.now();
}

async function hideThinkingIndicator() {
  const elapsed = Date.now() - thinkingShownAtMs;
  if (elapsed < MIN_THINKING_VISIBLE_MS) {
    await new Promise(resolve => setTimeout(resolve, MIN_THINKING_VISIBLE_MS - elapsed));
  }
  clearThinkingIndicatorNow();
}

function clearThinkingIndicatorNow() {
  if (thinkingMessageEl && thinkingMessageEl.parentNode) {
    thinkingMessageEl.parentNode.removeChild(thinkingMessageEl);
  }
  thinkingMessageEl = null;
  thinkingShownAtMs = 0;
}

function formatResult(result) {
  if (!result) return "No result.";
  if (result.error) return result.error;
  const n = result.entries_added != null ? result.entries_added : 0;
  const name = result.cohort_name || "cohort";
  let text = "Found " + n + " entries in cohort `" + name + "`. " + (result.message || "");
  const steps = result.raw && result.raw.steps;
  const mode = result.raw && result.raw.execution_mode;
  const toolPath = result.raw && result.raw.tool_path;
  const connectorPath = result.raw && result.raw.connector_path;
  const policyOutcomes = result.raw && result.raw.policy_outcomes;
  const memoryHits = result.raw && result.raw.memory_hits;
  const deadLetters = result.raw && result.raw.dead_letters;
  if (mode) {
    text += " Mode: " + mode + ".";
  }
  if (toolPath && toolPath.length) {
    text += " Tool path: " + toolPath.join(" -> ") + ".";
  }
  if (connectorPath && connectorPath.length) {
    text += " Connector path: " + connectorPath.join(" -> ") + ".";
  }
  if (steps && steps.length) {
    const parts = steps.map(st => (st.action || "?") + (st.entry_count != null ? " (" + st.entry_count + ")" : ""));
    text += " Steps: " + parts.join(", ");
  }
  if (policyOutcomes && policyOutcomes.length) {
    const policies = policyOutcomes.map(p => (p.action || "?") + "=" + (p.policy_decision || "allow"));
    text += " Policy: " + policies.join(", ") + ".";
  }
  if (memoryHits) {
    const shortCount = memoryHits.short_term ? memoryHits.short_term.length : 0;
    const longCount = memoryHits.long_term ? memoryHits.long_term.length : 0;
    text += " Memory hits: short=" + shortCount + ", long=" + longCount + ".";
  }
  if (deadLetters && deadLetters.length) {
    text += " Dead letters: " + deadLetters.length + ".";
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

// ── Cohorts sidebar (event delegation) ────────────────────
async function loadCohorts() {
  const list = document.getElementById("cohorts-list");
  const count = document.getElementById("cohort-count");

  // Remove old delegated handler if any, then add fresh one
  if (!list._cohortDelegateAttached) {
    list.addEventListener("click", (e) => {
      const item = e.target.closest(".cohort-item");
      if (item && item.dataset.name) {
        openArchives(item.dataset.name);
      }
    });
    list._cohortDelegateAttached = true;
  }

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
    // No per-item listeners needed — delegation handles clicks
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
      await loadWorkflowPanels();
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

  // Use event delegation for archive cohort items
  if (!cohortsEl._archiveDelegateAttached) {
    cohortsEl.addEventListener("click", (e) => {
      const item = e.target.closest(".cohort-item");
      if (item && item.dataset.name) {
        loadEntries(item.dataset.name, document.getElementById("archives-entries"));
      }
    });
    cohortsEl._archiveDelegateAttached = true;
  }

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
    // No per-item listeners needed — delegation handles clicks
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
  const banner = document.getElementById("backend-banner");
  const showBanner = function (text) {
    if (!banner) return;
    banner.textContent = text;
    banner.classList.remove("hidden");
  };
  const hideBanner = function () {
    if (banner) banner.classList.add("hidden");
  };
  try {
    const data = await API.health();
    const wf = data && data.api && data.api.workflows === true;
    if (wf) {
      el.textContent = "CONNECTED";
      el.classList.add("online");
      el.style.color = "";
      hideBanner();
    } else {
      el.textContent = "NEEDS UPDATE";
      el.classList.remove("online");
      el.style.color = "var(--amber)";
      showBanner(
        "Backend is up but running an old build (no task/note workflow API). On EC2: " +
          "cd ~/all-doing-bot && git pull origin main && source venv/bin/activate && " +
          "pip install -r apps/backend/requirements.txt && sudo systemctl restart alldoing — then hard-refresh."
      );
    }
  } catch (e) {
    el.textContent = "OFFLINE";
    el.classList.remove("online");
    el.style.color = "var(--red)";
    document.getElementById("sys-status").textContent = "DEGRADED";
    document.getElementById("sys-status").style.color = "var(--amber)";
    showBanner("Backend unreachable. Check EC2, security group, and BACKEND_URL in index.html. " + (e.message || e));
  }
}

// ── Sign out ──────────────────────────────────────────────
function initSignOut() {
  document.getElementById("signout-btn").addEventListener("click", () => {
    // Clean up intervals and abort in-flight requests
    stopClock();
    abortActiveRequest();
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
