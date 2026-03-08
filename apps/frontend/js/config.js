/**
 * Backend URL. Set window.BACKEND_URL in index.html (before this script) for production.
 * Localhost uses http://localhost:8000 automatically.
 */
var BACKEND_URL;
(function () {
  const isLocal = typeof window !== "undefined" && window.location.hostname === "localhost";
  const placeholder = "https://SET-BACKEND-URL-IN-INDEX-HTML";
  const url = window.BACKEND_URL || (isLocal ? "http://localhost:8000" : placeholder);
  window.BACKEND_URL = url;
  BACKEND_URL = url;
  if (!isLocal && url === placeholder) {
    console.error("[config] Set window.BACKEND_URL in index.html to your backend host (e.g. EC2 or Render URL).");
  }
})();
