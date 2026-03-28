# EC2 one-time backend setup (runbook)

**Instance:** `i-08f6fa1828d35071e`  
**Public DNS:** `ec2-54-165-94-30.compute-1.amazonaws.com`  
**Public IP:** `54.165.94.30`  
**Region:** us-east-1  

**Security group:** `launch-wizard-1` (ID: `sg-044282bf7d0c0d286`). Ports **22** (SSH) and **8000** are already open. You must **add 80 and 443** for Caddy/HTTPS:

1. AWS Console → **EC2** → **Security Groups** → open **launch-wizard-1** (`sg-044282bf7d0c0d286`).
2. **Edit inbound rules** → **Add rule**:
   - Type: **HTTP**, Port: **80**, Source: **0.0.0.0/0** (or “Anywhere-IPv4”).
   - **Add rule** again: Type: **HTTPS**, Port: **443**, Source: **0.0.0.0/0**.
3. **Save rules**. After a few seconds, `https://54-165-94-30.sslip.io/health` will be reachable.

This instance has **no key pair** in the launch config. Use **EC2 Instance Connect** in the AWS Console (Connect → EC2 Instance Connect) to get a browser shell, or attach a key and use SSH.

---

## 1. Connect

- **Option A:** AWS Console → EC2 → Instances → select instance → **Connect** → **EC2 Instance Connect** → **Connect** (browser shell).
- **Option B:** SSH with your key: `ssh -i your-key.pem ubuntu@ec2-54-165-94-30.compute-1.amazonaws.com` (user may be `ubuntu` or `ec2-user` depending on AMI).

### Permanent SSH from Windows (this PC)

1. **Key pair** (once per machine):  
   `ssh-keygen -t ed25519 -f %USERPROFILE%\.ssh\alldoing_ec2 -C "all-doing-ec2"`  
   (Repo deploy scripts expect **`%USERPROFILE%\.ssh\alldoing_ec2`**.)

2. **Install your public key on the instance** (while logged in via **EC2 Instance Connect** browser shell as `ubuntu`):

   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   echo 'PASTE_CONTENT_OF_alldoing_ec2.pub_ONE_LINE_HERE' >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

   Or open `nano ~/.ssh/authorized_keys` and paste the single line from `alldoing_ec2.pub`.

3. **SSH config on Windows** — create or edit **`%USERPROFILE%\.ssh\config`**:

   ```text
   Host all-doing-ec2
       HostName ec2-54-165-94-30.compute-1.amazonaws.com
       User ubuntu
       IdentityFile ~/.ssh/alldoing_ec2
       IdentitiesOnly yes
       StrictHostKeyChecking accept-new
   ```

   Amazon Linux images often use **`User ec2-user`** instead of `ubuntu`.

4. **Connect:** `ssh all-doing-ec2`

5. **Deploy script env** (PowerShell):  
   `$env:SSH_KEY = "$env:USERPROFILE\.ssh\alldoing_ec2"`  
   `$env:EC2_HOST = 'ec2-54-165-94-30.compute-1.amazonaws.com'`  
   then `Invoke-Ec2BackendUpdate.ps1`.

If `ssh` says the key is ignored, fix ACL on the private key (PowerShell as your user):

`icacls %USERPROFILE%\.ssh\alldoing_ec2 /inheritance:r`  
`icacls %USERPROFILE%\.ssh\alldoing_ec2 /grant:r "%USERNAME%:R"`

---

## 2. One-time setup (copy-paste into the shell)

Run as a user that can use `sudo` (e.g. `ubuntu`):

```bash
# Clone repo and run setup script
sudo apt-get update -qq && sudo apt-get install -y -qq git
sudo -u ubuntu git clone https://github.com/Mihirokte/all-doing-bot.git /home/ubuntu/all-doing-bot || (cd /home/ubuntu/all-doing-bot && sudo -u ubuntu git pull)
sudo bash /home/ubuntu/all-doing-bot/apps/backend/deploy/ec2-setup.sh
```

---

## 3. Configure .env

```bash
sudo -u ubuntu cp /home/ubuntu/all-doing-bot/.env.example /home/ubuntu/all-doing-bot/.env
sudo -u ubuntu nano /home/ubuntu/all-doing-bot/.env
```

Set at least:

- `REMOTE_LLM_API_KEY=<your-groq-key>`
- Optionally: `CORS_ALLOW_ORIGINS=https://mihirokte.github.io` (or your frontend URL)

Save and exit.

---

## 4. Start and enable the backend

```bash
sudo systemctl start alldoing
sudo systemctl enable alldoing
sudo systemctl status alldoing
```

---

## 5. Verify

```bash
curl -s http://localhost:8000/health
```

From your machine (after opening ports 80/443):

```bash
curl -s https://54-165-94-30.sslip.io/health
```

Should return `{"status":"ok"}`. Frontend should use `BACKEND_URL=https://54-165-94-30.sslip.io`.

---

## Later: update code and restart (mandate for this repo)

**Preferred (matches GitHub Actions):** pull `origin/main` on the instance, install deps, restart `alldoing` — see `ec2-pull-restart.sh`.

From your laptop **with SSH**:

```bash
export EC2_HOST=ec2-54-165-94-30.compute-1.amazonaws.com
export EC2_USER=ubuntu   # or ec2-user on Amazon Linux
# export SSH_KEY=~/.ssh/your-key.pem
bash apps/backend/deploy/ec2-ssh-pull-restart-from-local.sh
```

**Windows (PowerShell):**

```powershell
$env:EC2_HOST = 'ec2-54-165-94-30.compute-1.amazonaws.com'
$env:SSH_KEY = "$env:USERPROFILE\.ssh\your-key.pem"   # if needed
powershell -NoProfile -ExecutionPolicy Bypass -File apps/backend/deploy/Invoke-Ec2BackendUpdate.ps1
```

**Full rsync + restart** (when you need to push uncommitted files): `apps/backend/deploy/deploy-from-local.sh`.

Or **GitHub Actions** → **Deploy backend (EC2)** → **Run workflow** (requires secrets `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`).

On the instance manually:

```bash
bash /home/ubuntu/all-doing-bot/apps/backend/deploy/ec2-pull-restart.sh
```
