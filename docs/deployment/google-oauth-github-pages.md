# Google OAuth for GitHub Pages (fix “Error 401: invalid_client”)

The frontend uses Google Sign-In. If you see **“The OAuth client was not found”** or **“Error 401: invalid_client”**, the OAuth client is missing or not configured for your GitHub Pages URL.

## 1. Create an OAuth 2.0 Client ID

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select (or create) a project.
2. Go to **APIs & Services** → **Credentials**.
3. Click **Create credentials** → **OAuth client ID**.
4. If asked, configure the **OAuth consent screen** (External, add your email, add scope `email` / `profile` if needed).
5. Application type: **Web application**.
6. **Name:** e.g. “all-doing-bot”.
7. Under **Authorized JavaScript origins**, add:
   - `https://mihirokte.github.io`
   - (Optional) `http://localhost:3000` for local testing.
8. Leave **Authorized redirect URIs** empty for Google One Tap / Sign-In (no redirect).
9. Click **Create**. Copy the **Client ID** (ends with `.apps.googleusercontent.com`).

## 2. Set the Client ID in the frontend

1. In the repo, open **`apps/frontend/index.html`**.
2. Find the line:
   ```html
   <!-- <script>window.GOOGLE_CLIENT_ID = "your-oauth-client-id.apps.googleusercontent.com";</script> -->
   ```
3. **Uncomment** it and replace the placeholder with your real Client ID:
   ```html
   <script>window.GOOGLE_CLIENT_ID = "123456789-xxxx.apps.googleusercontent.com";</script>
   ```
4. Commit, push to `main`, then redeploy the frontend to GitHub Pages:
   ```bash
   git add apps/frontend/index.html
   git commit -m "Set Google OAuth client ID for GitHub Pages"
   git push origin main
   git subtree push --prefix apps/frontend origin gh-pages
   ```

After redeploy, reload `https://mihirokte.github.io/all-doing-bot/` and try Sign in with Google again. The client ID is safe to commit (it is public); do not commit a client *secret* if you ever add server-side OAuth flows.
