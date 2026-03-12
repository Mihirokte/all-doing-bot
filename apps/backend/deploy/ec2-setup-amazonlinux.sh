#!/usr/bin/env bash
# One-time EC2 setup for Amazon Linux (yum/dnf). Run with sudo.
# Usage: sudo bash ec2-setup-amazonlinux.sh [REPO_URL]
# Prereq: Expand EBS volume to 20 GB if using Ollama (see docs/deployment/ec2-expand-volume.md).

set -euo pipefail

APP_USER="${APP_USER:-ec2-user}"
APP_HOME="/home/${APP_USER}"
REPO_DIR="${APP_HOME}/all-doing-bot"
REPO_URL="${1:-https://github.com/Mihirokte/all-doing-bot.git}"
SERVICE_NAME="alldoing"

echo "[ec2-setup] Installing system packages (yum/dnf)..."
if command -v dnf &>/dev/null; then
  dnf install -y python3 python3-devel git gcc gcc-c++ cmake
else
  yum install -y python3 python3-devel git gcc gcc-c++ cmake
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

echo "[ec2-setup] Adding swap (2 GB) if missing..."
bash "$REPO_DIR/apps/backend/deploy/ec2-add-swap.sh" 2>/dev/null || true

echo "[ec2-setup] Installing Ollama..."
if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
  mkdir -p /etc/systemd/system/ollama.service.d
  cp "$REPO_DIR/apps/backend/deploy/ollama-override.conf" /etc/systemd/system/ollama.service.d/override.conf 2>/dev/null || true
  systemctl daemon-reload
  systemctl restart ollama
  systemctl enable ollama
fi
echo "[ec2-setup] Pulling Ollama model qwen3.5:4b (requires ~3.4 GB disk)..."
sudo -u "$APP_USER" ollama pull qwen3.5:4b 2>/dev/null || echo "[ec2-setup] Ollama pull failed (expand disk to 20 GB and run: ollama pull qwen3.5:4b)"

echo "[ec2-setup] Installing SearXNG (web search)..."
SEARX_DIR="${APP_HOME}/searxng"
if [[ ! -d "$SEARX_DIR" ]]; then
  sudo -u "$APP_USER" git clone --depth 1 https://github.com/searxng/searxng.git "$SEARX_DIR"
  sudo -u "$APP_USER" python3 -m venv "${SEARX_DIR}/venv"
  sudo -u "$APP_USER" "${SEARX_DIR}/venv/bin/pip" install -q --upgrade pip
  sudo -u "$APP_USER" bash -c "cd $SEARX_DIR && ./venv/bin/pip install -q -e ."
  mkdir -p /etc/searxng
  cp "$REPO_DIR/apps/backend/deploy/searxng-settings.yml" /etc/searxng/settings.yml 2>/dev/null || true
  cat > /etc/systemd/system/searxng.service << 'SEARXEOF'
[Unit]
Description=SearXNG metasearch (JSON API for web search)
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/searxng
Environment="SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml"
ExecStart=/home/ec2-user/searxng/venv/bin/python /home/ec2-user/searxng/manage run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SEARXEOF
  systemctl daemon-reload
  systemctl enable searxng
  systemctl start searxng
fi

echo "[ec2-setup] Done. Next: create .env (copy from .env.example), set LLM_PROVIDER_PRIORITY=ollama,local,remote,mock, then sudo systemctl start $SERVICE_NAME && sudo systemctl enable $SERVICE_NAME"