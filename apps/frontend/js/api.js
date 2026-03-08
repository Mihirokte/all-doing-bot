/** Backend API client. */
const API = {
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
