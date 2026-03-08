#!/usr/bin/env bash
# One-time EC2 setup: install Python, venv, clone repo, deps, systemd.
# Run on Ubuntu (e.g. 22.04) as a user with sudo. Paths assume app user 'ubuntu' and app at /home/ubuntu/all-doing-bot.
# Usage: sudo bash ec2-setup.sh [REPO_URL]
#   REPO_URL defaults to https://github.com/Mihirokte/all-doing-bot.git

set -euo pipefail

APP_USER="${APP_USER:-ubuntu}"
APP_HOME="/home/${APP_USER}"
REPO_DIR="${APP_HOME}/all-doing-bot"
REPO_URL="${1:-https://github.com/Mihirokte/all-doing-bot.git}"
SERVICE_NAME="alldoing"

echo "[ec2-setup] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  python3 \
  python3-pip \
  python3-venv \
  git \
  curl

echo "[ec2-setup] Setting up app directory and repo..."
if [[ ! -d "$REPO_DIR" ]]; then
  sudo -u "$APP_USER" git clone "$REPO_URL" "$REPO_DIR"
else
  (cd "$REPO_DIR" && sudo -u "$APP_USER" git fetch origin && sudo -u "$APP_USER" git reset --hard origin/main || true)
fi

echo "[ec2-setup] Creating venv and installing dependencies..."
sudo -u "$APP_USER" python3 -m venv "${REPO_DIR}/venv"
sudo -u "$APP_USER" "${REPO_DIR}/venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "${REPO_DIR}/venv/bin/pip" install -q -r "${REPO_DIR}/apps/backend/requirements.txt"

echo "[ec2-setup] Installing systemd unit..."
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=all-doing-bot FastAPI backend
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$REPO_DIR
Environment="PYTHONPATH=$REPO_DIR"
Environment="PATH=${REPO_DIR}/venv/bin:/usr/bin:/bin"
ExecStart=${REPO_DIR}/venv/bin/uvicorn apps.backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload

echo "[ec2-setup] Done. Next steps:"
echo "  1. Create ${REPO_DIR}/.env (copy from .env.example, set REMOTE_LLM_API_KEY etc.)"
echo "  2. If using Google Sheets, put credentials JSON on the server and set GOOGLE_CREDS_PATH"
echo "  3. Start and enable: sudo systemctl start $SERVICE_NAME && sudo systemctl enable $SERVICE_NAME"
echo "  4. Check: curl -s http://localhost:8000/health"
