/** Set window.GOOGLE_CLIENT_ID in index.html for production. OAuth client must be registered for your GitHub Pages domain. */
const CLIENT_ID = typeof window !== "undefined" && window.GOOGLE_CLIENT_ID
  ? window.GOOGLE_CLIENT_ID
  : "YOUR_GOOGLE_CLIENT_ID_HERE";

const LOGIN_CACHE_KEY = "allDoingBotLoggedInAt";
const LOGIN_CACHE_DAYS = 30;

let isAuthenticated = false;

function isLocalHost() {
  return typeof window !== "undefined" && window.location.hostname === "localhost";
}

function persistLogin() {
  try {
    localStorage.setItem(LOGIN_CACHE_KEY, String(Date.now()));
  } catch (e) {
    console.warn("[auth] localStorage not available:", e.message);
  }
}

function hasValidCachedLogin() {
  try {
    const raw = localStorage.getItem(LOGIN_CACHE_KEY);
    if (!raw) return false;
    const loggedInAt = parseInt(raw, 10);
    if (isNaN(loggedInAt)) return false;
    const maxAgeMs = LOGIN_CACHE_DAYS * 24 * 60 * 60 * 1000;
    return Date.now() - loggedInAt < maxAgeMs;
  } catch (e) {
    return false;
  }
}

function clearLoginCache() {
  try {
    localStorage.removeItem(LOGIN_CACHE_KEY);
  } catch (e) {}
}

function handleCredentialResponse(response) {
    if (typeof response.credential === "string") {
      console.log("Google Sign-In successful.");
    }
    isAuthenticated = true;
    persistLogin();
    unlockSystem();
}

function initGoogleAuth() {
    var restoredFromCache = hasValidCachedLogin();
    if (restoredFromCache) {
      isAuthenticated = true;
      unlockSystem();
    }

    if (window.google && window.google.accounts) {
        window.google.accounts.id.initialize({
            client_id: CLIENT_ID,
            callback: handleCredentialResponse
        });
        window.google.accounts.id.renderButton(
            document.getElementById("g_id_onload"),
            { theme: "outline", size: "large" }
        );
        if (!restoredFromCache) {
          window.google.accounts.id.prompt();
        }
    } else {
        console.error("Google library not loaded.");
    }
}

function unlockSystem() {
    document.getElementById('login-overlay').style.display = 'none';
    document.getElementById('game-container').style.display = 'block';
    
    // Notify the game that systems are active
    if (window.gameInterface && window.gameInterface.systemUnlock) {
        window.gameInterface.systemUnlock();
    }
}

// Optional: call from console or a "Sign out" button to clear saved login and reload
window.clearAllDoingLoginCache = function () {
  clearLoginCache();
  window.location.reload();
};

// Dev Bypass — only on localhost; hidden and disabled in production
var devBypassBtn = document.getElementById('dev-bypass-btn');
if (devBypassBtn) {
    if (!isLocalHost()) {
        devBypassBtn.style.display = 'none';
    } else {
        devBypassBtn.addEventListener('click', () => {
            console.log("Bypassing auth for dev purposes.");
            isAuthenticated = true;
            unlockSystem();
        });
    }
}
