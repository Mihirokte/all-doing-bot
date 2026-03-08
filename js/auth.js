/** Set window.GOOGLE_CLIENT_ID in index.html for production, or replace below. OAuth client must be registered for your GitHub Pages domain. */
const CLIENT_ID = typeof window !== "undefined" && window.GOOGLE_CLIENT_ID
  ? window.GOOGLE_CLIENT_ID
  : "YOUR_GOOGLE_CLIENT_ID_HERE";

let isAuthenticated = false;

function isLocalHost() {
  return typeof window !== "undefined" && window.location.hostname === "localhost";
}

function handleCredentialResponse(response) {
    console.log("Encoded JWT ID token: " + response.credential);
    // In a real app, send this token to your backend for verification
    isAuthenticated = true;
    unlockSystem();
}

function initGoogleAuth() {
    // If the library loaded
    if (window.google && window.google.accounts) {
        window.google.accounts.id.initialize({
            client_id: CLIENT_ID,
            callback: handleCredentialResponse
        });
        window.google.accounts.id.renderButton(
            document.getElementById("g_id_onload"),
            { theme: "outline", size: "large" }  // customization attributes
        );
        window.google.accounts.id.prompt(); // also display the One Tap dialog
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
