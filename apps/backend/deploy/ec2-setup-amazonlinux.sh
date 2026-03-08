#!/usr/bin/env bash
# One-time EC2 setup for Amazon Linux (yum/dnf). Run with sudo.
# Usage: sudo bash ec2-setup-amazonlinux.sh [REPO_URL]

set -euo pipefail

APP_USER="${APP_USER:-ec2-user}"
APP_HOME="/home/${APP_USER}"
REPO_DIR="${APP_HOME}/all-doing-bot"
REPO_URL="${1:-https://github.com/Mihirokte/all-doing-bot.git}"
SERVICE_NAME="alldoing"

echo "[ec2-setup] Installing system packages (yum/dnf)..."
# Install only git (and python3 if missing). Do not install 'curl' — it conflicts with curl-minimal on AL2023.
if command -v dnf &>/dev/null; then
  dnf install -y python3 git
else
  yum install -y python3 git
fi

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

echo "[ec2-setup] Done. Next: create .env, then sudo systemctl start $SERVICE_NAME && sudo systemctl enable $SERVICE_NAME"