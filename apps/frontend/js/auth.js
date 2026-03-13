/** Auth: Google Sign-In with 30-day login cache. No Phaser dependency. */

const CLIENT_ID = typeof window !== "undefined" && window.GOOGLE_CLIENT_ID
  ? window.GOOGLE_CLIENT_ID
  : "YOUR_GOOGLE_CLIENT_ID_HERE";

const LOGIN_CACHE_KEY  = "allDoingBotLoggedInAt";
const LOGIN_CACHE_DAYS = 30;

let isAuthenticated = false;

function isLocalHost() {
  return typeof window !== "undefined" &&
    (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");
}

function persistLogin() {
  try { localStorage.setItem(LOGIN_CACHE_KEY, String(Date.now())); }
  catch (e) { console.warn("[auth] localStorage unavailable:", e.message); }
}

function hasValidCachedLogin() {
  try {
    const raw = localStorage.getItem(LOGIN_CACHE_KEY);
    if (!raw) return false;
    const t = parseInt(raw, 10);
    if (isNaN(t)) return false;
    return Date.now() - t < LOGIN_CACHE_DAYS * 86400000;
  } catch (e) { return false; }
}

function clearLoginCache() {
  try { localStorage.removeItem(LOGIN_CACHE_KEY); } catch (e) {}
}

function handleCredentialResponse(response) {
  if (typeof response.credential === "string") {
    console.log("[auth] Google Sign-In OK");
  }
  isAuthenticated = true;
  persistLogin();
  unlockSystem();
}

function unlockSystem() {
  document.getElementById("login-overlay").style.display = "none";
  document.getElementById("terminal-root").style.display  = "flex";
  document.getElementById("terminal-root").style.flexDirection = "column";
  if (typeof window.appBoot === "function") window.appBoot();
}

function initGoogleAuth() {
  // Show dev bypass only on localhost
  const devBtn = document.getElementById("dev-bypass-btn");
  if (devBtn) {
    if (isLocalHost()) {
      devBtn.classList.add("visible");
      devBtn.addEventListener("click", () => {
        isAuthenticated = true;
        unlockSystem();
      });
    }
  }

  const fromCache = hasValidCachedLogin();
  if (fromCache) {
    isAuthenticated = true;
    unlockSystem();
    return;
  }

  if (window.google && window.google.accounts) {
    window.google.accounts.id.initialize({
      client_id: CLIENT_ID,
      callback: handleCredentialResponse,
    });
    window.google.accounts.id.renderButton(
      document.getElementById("g_id_onload"),
      { theme: "filled_black", size: "large", text: "sign_in_with" }
    );
    window.google.accounts.id.prompt();
  } else {
    console.error("[auth] Google library not loaded");
  }
}

// Expose sign-out helper
window.clearAllDoingLoginCache = function () {
  clearLoginCache();
  window.location.reload();
};
