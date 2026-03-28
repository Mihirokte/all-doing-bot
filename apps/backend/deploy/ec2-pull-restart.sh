#!/usr/bin/env bash
# Run ON the EC2 instance after SSH, OR pipe into SSH:  ssh user@host 'bash -s' < ec2-pull-restart.sh
# Default repo path matches GitHub Actions deploy-ec2.yml (Ubuntu: /home/ubuntu/..., Amazon Linux: /home/ec2-user/...).
# Override: REPO_DIR=/path/to/all-doing-bot bash ec2-pull-restart.sh
# Use a Python 3.10+ venv: langgraph and mcp require 3.10+.
set -euo pipefail
REPO_DIR="${REPO_DIR:-/home/${USER}/all-doing-bot}"
cd "$REPO_DIR"
git fetch origin main
git reset --hard origin/main
source venv/bin/activate
pip install -r apps/backend/requirements.txt
sudo systemctl restart alldoing
sleep 2
echo "--- /health ---"
curl -sS "http://127.0.0.1:8000/health" | head -c 500
echo ""
echo "--- workflow probe (expect JSON array) ---"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "http://127.0.0.1:8000/workflows/tasks?session_key=smoke&limit=1"
echo "Done. If workflow probe is not HTTP 200, check: journalctl -u alldoing -n 80 --no-pager"
