# AWS Credentials and EC2 Deploy Guide

This guide covers: (1) creating credentials so deploy agents can access your AWS account, (2) optional IAM roles, (3) keeping your EC2 instance updated with the latest code, and (4) one-time EC2 setup.

**Free tier only:** The repo’s IAM setup (`setup_aws_iam.py` / `setup-aws-iam.sh`) grants **only EC2 read-only** (describe instances/tags). No SSM, S3, Lambda, RDS, or any other paid service. Deploy is via SSH. Do not attach an IAM role to the EC2 instance if you want to avoid any non–free-tier usage.

---

## 1. Who needs credentials?

| Actor | Purpose | Recommended auth |
|-------|---------|-------------------|
| **You / local machine** | Deploy from your laptop (rsync + SSH or AWS CLI) | IAM user access keys → `~/.aws/credentials` |
| **GitHub Actions** | Deploy on push to `main` | IAM OIDC role (no long‑lived keys) or IAM user keys in GitHub Secrets |
| **EC2 instance (the app)** | If the app calls AWS APIs (e.g. S3, Secrets Manager) | IAM instance profile (role attached to EC2) — no keys on disk |

For “give all agents access,” we create **one IAM user** (e.g. `deploy-agent`) with a **minimal policy**, then use its keys for local and/or CI. Optionally add a **GitHub OIDC role** so Actions don’t need keys.

---

## 2. Create an IAM user for deploy agents

### 2.1 Create the user

1. In AWS Console: **IAM** → **Users** → **Create user**.
2. User name: e.g. `deploy-agent` (or `github-actions-deploy`).
3. **Do not** check “Provide user access to the AWS Management Console” if agents only need API access (recommended for automation).
4. Create user.

### 2.2 Attach a minimal policy (free tier: EC2 only)

For **free tier only**, agents get **only EC2 read-only** (describe instances/tags). No SSM, S3, or any other service. Deploy is via SSH; IAM is only used to resolve instance IP (e.g. for `deploy-from-local.sh`).

Policy used by `setup_aws_iam.py`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DescribeEC2Only",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeTags"
      ],
      "Resource": "*"
    }
  ]
}
```

Create a **customer-managed policy** (e.g. `DeployAgentPolicy`) with the above, then attach it to the user `deploy-agent`. Do **not** attach an IAM role to the EC2 instance if you want to stay within free tier only (no SSM, no other AWS APIs from the box).

### 2.3 Create access keys for the user

1. IAM → **Users** → **deploy-agent** → **Security credentials**.
2. **Create access key** → use case “Command Line Interface (CLI)”.
3. Store the **Access key ID** and **Secret access key** securely (you won’t see the secret again).

---

## 3. Credentials file for agents (local / scripts)

Any agent (your laptop, a runner) that uses the AWS CLI or SDK needs the keys. Standard place is the **AWS credentials file**.

### 3.1 Format

Location:

- **Linux/macOS:** `~/.aws/credentials`
- **Windows:** `%USERPROFILE%\.aws\credentials`

Example (one profile):

```ini
[deploy-agent]
aws_access_key_id = AKIA......................
aws_secret_access_key = ................................................
```

Optional: set default region in `~/.aws/config`:

```ini
[profile deploy-agent]
region = us-east-1
```

### 3.2 How agents use it

- **AWS CLI:**  
  `export AWS_PROFILE=deploy-agent`  
  then e.g. `aws ec2 describe-instances ...`
- **Scripts / automation:**  
  Set env vars (prefer over putting keys in the file on shared machines):
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_DEFAULT_REGION` (e.g. `us-east-1`)
- **GitHub Actions:**  
  Store the two keys as repository **Secrets** (e.g. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`), then in the workflow set those env vars so the CLI/SDK picks them up.

Never commit the credentials file or the secret key to git.

---

## 4. (Optional) IAM role for GitHub Actions (OIDC, no keys)

To avoid long‑lived access keys in GitHub:

1. In IAM, create an **OIDC identity provider** for GitHub (e.g. `token.actions.githubusercontent.com`).
2. Create an IAM **role** for “Web identity” with GitHub as provider; trust policy allows your repo (and optionally only `main`).
3. Attach the same minimal policy (describe EC2 + optional SSM) to this role.
4. In the GitHub workflow, use `aws-actions/configure-aws-credentials@v4` with `role-to-assume: arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME`.

Then you don’t need `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in Secrets. Official docs: [Configuring OpenID Connect in AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services).

---

## 5. (Optional) IAM role for the EC2 instance

**Free tier only:** Do **not** attach any IAM role to the EC2 instance. That way the instance has no permissions to call any AWS service (no SSM, S3, etc.). Deploy and access are via SSH only.

If you previously ran the IAM setup when it created `AllDoingEC2Role`, you can remove it: IAM → **Roles** → **AllDoingEC2Role** → delete; detach it from any instance first. IAM → **Instance profiles** → delete `AllDoingEC2Role` if present.

If later you want the app on EC2 to call AWS (e.g. S3, Secrets Manager), create a role with only those minimal permissions and attach it to the instance.

---

## 6. Keeping EC2 updated with latest code

Pick one main flow.

### 6.1 Option A — Deploy from your machine (SSH + rsync/git)

1. Put the **deploy-agent** keys in `~/.aws/credentials` (or env) so you can resolve the instance (e.g. by tag).
2. Ensure EC2 has your **SSH public key** (launch with a key pair or add via userdata).
3. Run the deploy script from the repo (see below), which will:
   - rsync the repo (or `git pull` on the server) and restart the service.

No GitHub Actions needed; “agents” here are you or a script on your machine.

### 6.2 Option B — GitHub Actions deploys on push

1. Store `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (or use OIDC role) in GitHub Secrets.
2. Store **SSH private key** for the EC2 user (e.g. `ubuntu`) as a secret (e.g. `EC2_SSH_KEY`).
3. In the workflow: checkout repo, then either:
   - **SSH:** use the key to `rsync` + `ssh 'systemctl restart alldoing'`, or
   - **SSM:** use AWS CLI to run `SendCommand` with `AWS-RunShellScript` to `cd /home/ubuntu/all-doing-bot && git pull && systemctl restart alldoing`.

### 6.3 Option C — EC2 pulls on a schedule

On the instance, cron as the app user:

```cron
*/5 * * * * cd /home/ubuntu/all-doing-bot && git pull && systemctl --user restart alldoing  # or systemctl restart alldoing if system-wide
```

No IAM deploy user needed for “push”; only for your own SSH or SSM. Agents that only need to “know” the instance can use the minimal describe-only policy.

---

## 7. One-time EC2 setup (summary)

These steps get the backend running on a new EC2 (Ubuntu or Amazon Linux 2).

1. **Launch EC2**  
   - AMI: Ubuntu 22.04 (or Amazon Linux 2).  
   - Instance type: e.g. t2.micro (free tier).  
   - Security group: SSH (22) from your IP; HTTP (80) / HTTPS (443) if you put a reverse proxy in front.

2. **IAM role for the instance**  
   - Optional but recommended if you use SSM: attach a role with `AmazonSSMManagedInstanceCore` so SSM Agent can run without SSH.

3. **First login and system setup**  
   - SSH in, then run the **EC2 setup script** from this repo (see [EC2 setup script](#8-ec2-setup-script) below). It installs Python 3, venv, clones the repo, installs dependencies, and installs systemd service. It does **not** create `.env` (you do that manually with secrets).

4. **Configure the app**  
   - Copy `.env.example` to `.env` on the server and fill in at least:
     - `REMOTE_LLM_API_KEY`
     - Optionally `GOOGLE_CREDS_PATH`, `SPREADSHEET_ID`, `CORS_ALLOW_ORIGINS`
   - Put the Google service account JSON on the server if using Sheets (path set in `GOOGLE_CREDS_PATH`).

5. **Start and enable the service**  
   - `sudo systemctl start alldoing && sudo systemctl enable alldoing`

6. **Health check**  
   - Use the provided `health_check.sh` from cron (see `apps/backend/deploy/health_check.sh`).

---

## 8. EC2 setup script

Run this on a **fresh** Ubuntu EC2 (as a user that can use `sudo`). It installs Python 3, creates a venv, clones the repo, installs dependencies, and installs the systemd unit. Paths assume app at `/home/ubuntu/all-doing-bot` and service name `alldoing`.

See: **`apps/backend/deploy/ec2-setup.sh`** in this repo. Usage:

```bash
# On the EC2 instance (after cloning the repo once, or copy the script there)
sudo bash /path/to/ec2-setup.sh
```

Then create `.env` and start the service as in section 7.

---

## 9. Deploy script (for agents / you)

A script that **updates** the app on EC2 and restarts it (run from your machine or CI):

- **`apps/backend/deploy/deploy-from-local.sh`** — Uses SSH: syncs repo (or triggers `git pull` on server) and restarts `alldoing`. Requires `EC2_HOST` (or IP) and SSH key. Optionally uses AWS CLI to resolve instance IP by tag.

Use this from your laptop or from GitHub Actions (with SSH key and host in secrets).

---

## 10. Quick reference

| Goal | Action |
|------|--------|
| Let agents (you/CI) access AWS | Create IAM user `deploy-agent`, attach minimal policy, create access key. Put keys in `~/.aws/credentials` or GitHub Secrets. |
| No long-lived keys in GitHub | Add IAM OIDC provider for GitHub, create role, use `configure-aws-credentials` with `role-to-assume`. |
| EC2 app calls AWS APIs | Attach IAM role (instance profile) to EC2. |
| Update code on EC2 | Use deploy script (SSH) or GitHub Actions (SSH/SSM) or cron `git pull` on the server. |
| First-time EC2 setup | Run `apps/backend/deploy/ec2-setup.sh`, then add `.env` and start `alldoing` service. |

---

## 11. Security checklist

- [ ] IAM user has only the permissions it needs (describe EC2 and, if used, SSM).
- [ ] Access key is not committed to the repo; use `~/.aws/credentials` or env vars / secrets.
- [ ] EC2 security group allows SSH only from known IPs (or use SSM and lock down SSH).
- [ ] `.env` on the server is not in the repo; add to `.gitignore` and set file permissions (e.g. `chmod 600 .env`).
