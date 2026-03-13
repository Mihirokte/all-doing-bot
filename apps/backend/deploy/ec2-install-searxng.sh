#!/usr/bin/env bash
# Install and start SearXNG on EC2 (run on host as ec2-user, then sudo for systemd).
set -euo pipefail
SEARX_DIR="${HOME}/searxng"
REPO_DIR="${HOME}/all-doing-bot"
if [[ ! -d "$SEARX_DIR" ]]; then
  git clone --depth 1 https://github.com/searxng/searxng.git "$SEARX_DIR"
  python3 -m venv "${SEARX_DIR}/venv"
  "${SEARX_DIR}/venv/bin/pip" install -q --upgrade pip
  (cd "$SEARX_DIR" && ./venv/bin/pip install -q -e .)
fi
sudo mkdir -p /etc/searxng
sudo cp "${REPO_DIR}/apps/backend/deploy/searxng-settings.yml" /etc/searxng/settings.yml 2>/dev/null || true
sudo tee /etc/systemd/system/searxng.service > /dev/null << 'SEARXEOF'
[Unit]
Description=SearXNG metasearch (JSON API for web search)
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/searxng
Environment=SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml
ExecStart=/home/ec2-user/searxng/venv/bin/python /home/ec2-user/searxng/manage run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SEARXEOF
sudo systemctl daemon-reload
sudo systemctl enable searxng
sudo systemctl start searxng
sudo systemctl status searxng --no-pager
