# EC2 one-time backend setup (runbook)

**Instance:** `i-08f6fa1828d35071e`  
**Public DNS:** `ec2-54-165-94-30.compute-1.amazonaws.com`  
**Public IP:** `54.165.94.30`  
**Region:** us-east-1  

Port **22** (SSH) and **8000** (backend) are open.

This instance has **no key pair** in the launch config. Use **EC2 Instance Connect** in the AWS Console (Connect → EC2 Instance Connect) to get a browser shell, or attach a key and use SSH.

---

## 1. Connect

- **Option A:** AWS Console → EC2 → Instances → select instance → **Connect** → **EC2 Instance Connect** → **Connect** (browser shell).
- **Option B:** SSH with your key: `ssh -i your-key.pem ubuntu@ec2-54-165-94-30.compute-1.amazonaws.com` (user may be `ubuntu` or `ec2-user` depending on AMI).

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

From your machine:

```bash
curl -s http://54.165.94.30:8000/health
```

Should return `{"status":"ok"}`.

---

## Later: update code and restart

From your laptop (with SSH key):

```bash
export EC2_HOST=ec2-54-165-94-30.compute-1.amazonaws.com
# export SSH_KEY=path/to/your-key.pem   # if not default
bash apps/backend/deploy/deploy-from-local.sh
```

Or on the instance:

```bash
cd /home/ubuntu/all-doing-bot && sudo -u ubuntu git pull && sudo systemctl restart alldoing
```
