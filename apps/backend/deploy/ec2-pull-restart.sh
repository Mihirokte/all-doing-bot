#!/usr/bin/env bash
# Run ON the EC2 instance (ubuntu) after SSH. Updates repo, deps, restarts alldoing.
set -euo pipefail
cd /home/ubuntu/all-doing-bot
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
