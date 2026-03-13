/** Main UI: query input, status polling, cohort list, entry viewer */
(function () {
  const queryInput = document.getElementById("query-input");
  const submitBtn = document.getElementById("submit-btn");
  const statusEl = document.getElementById("status");
  const resultEl = document.getElementById("result");
  const cohortsEl = document.getElementById("cohorts-list");
  const entriesEl = document.getElementById("entries");
  const cohortTitleEl = document.getElementById("cohort-title");

  let pollInterval = null;

  function setStatus(msg, isError = false) {
    if (statusEl) {
      statusEl.textContent = msg;
      statusEl.className = "status " + (isError ? "error" : "");
    }
    if (window.gameInterface) {
      window.gameInterface.setStatus(msg, isError);
    }
  }

  function setResult(html) {
    if (resultEl) resultEl.innerHTML = html;
  }

  async function pollStatus(taskId) {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
      try {
        const d = await API.getStatus(taskId);
        setStatus("Status: " + d.status);
        if (d.status === "completed") {
          clearInterval(pollInterval);
          pollInterval = null;
          setResult(
            "<pre>" + JSON.stringify(d.result || {}, null, 2) + "</pre>"
          );
          if (window.gameInterface) window.gameInterface.addPoints(50);
          setStatus("Process Complete. Result obtained.");
          loadCohorts();
        } else if (d.status === "failed") {
          clearInterval(pollInterval);
          pollInterval = null;
          setStatus("Failed: " + (d.result && d.result.error ? d.result.error : "unknown"), true);
          setResult("<pre>" + JSON.stringify(d.result || {}, null, 2) + "</pre>");
        }
      } catch (e) {
        setStatus("Error: " + e.message, true);
      }
    }, 2000);
  }

  async function onSubmit() {
    const q = (queryInput && queryInput.value || "").trim();
    if (!q) return;
    submitBtn.disabled = true;
    setStatus("Submitting...");
    setResult("");
    try {
      const { task_id } = await API.submitQuery(q);
      setStatus("Processing (task " + task_id.slice(0, 8) + "...)");
      await pollStatus(task_id);
    } catch (e) {
      setStatus("Error: " + e.message, true);
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function loadCohorts() {
    if (!cohortsEl) return;
    try {
      const list = await API.listCohorts();
      cohortsEl.innerHTML = list.length
        ? list
            .map(
              (c) =>
                '<button type="button" class="cohort-btn" data-name="' +
                escapeHtml(c.cohort_name) +
                '">' +
                escapeHtml(c.cohort_name) +
                " (" +
                (c.entry_count || 0) +
                ")</button>"
            )
            .join("")
        : "<p>No cohorts yet.</p>";
      cohortsEl.querySelectorAll(".cohort-btn").forEach((btn) => {
        btn.addEventListener("click", () => showCohort(btn.dataset.name));
      });
    } catch (e) {
      cohortsEl.innerHTML = "<p>Failed to load cohorts.</p>";
    }
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  async function showCohort(name) {
    if (!entriesEl || !cohortTitleEl) return;
    cohortTitleEl.textContent = "Entries: " + name;
    entriesEl.innerHTML = "Loading...";
    try {
      const entries = await API.getCohortEntries(name);
      entriesEl.innerHTML = entries.length
        ? "<table><thead><tr><th>ID</th><th>Content</th><th>Source</th></tr></thead><tbody>" +
          entries
            .map(
              (e) =>
                "<tr><td>" +
                e.entry_id +
                "</td><td>" +
                escapeHtml((e.content || "").slice(0, 200)) +
                "</td><td>" +
                escapeHtml(e.source || "") +
                "</td></tr>"
            )
            .join("") +
          "</tbody></table>"
        : "<p>No entries.</p>";
    } catch (e) {
      entriesEl.innerHTML = "<p>Failed to load entries.</p>";
    }
  }

  if (submitBtn && queryInput) {
    submitBtn.addEventListener("click", onSubmit);
    queryInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") onSubmit();
    });
  }

  // Expose to game.js
  window.appRefreshCohorts = loadCohorts;

  loadCohorts();
})();
