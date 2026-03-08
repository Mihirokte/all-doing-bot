#!/usr/bin/env bash
# One-time setup: run on the EC2 instance (e.g. via EC2 Instance Connect) as a user with sudo.
# After this, edit /home/ubuntu/all-doing-bot/.env (set REMOTE_LLM_API_KEY, optional CORS_ALLOW_ORIGINS) then start the service.

set -e

echo "[1/5] Installing git..."
sudo apt-get update -qq && sudo apt-get install -y -qq git

echo "[2/5] Cloning or updating repo..."
if [[ ! -d /home/ubuntu/all-doing-bot ]]; then
  sudo -u ubuntu git clone https://github.com/Mihirokte/all-doing-bot.git /home/ubuntu/all-doing-bot
else
  (cd /home/ubuntu/all-doing-bot && sudo -u ubuntu git fetch origin && sudo -u ubuntu git reset --hard origin/main)
fi

echo "[3/5] Running ec2-setup.sh..."
sudo bash /home/ubuntu/all-doing-bot/apps/backend/deploy/ec2-setup.sh

echo "[4/5] Creating .env from example..."
sudo -u ubuntu cp /home/ubuntu/all-doing-bot/.env.example /home/ubuntu/all-doing-bot/.env
echo "      -> Edit /home/ubuntu/all-doing-bot/.env and set REMOTE_LLM_API_KEY (and optionally CORS_ALLOW_ORIGINS), then run:"
echo "      sudo systemctl start alldoing && sudo systemctl enable alldoing"
echo "      curl -s http://localhost:8000/health"

echo "[5/5] Starting and enabling service..."
sudo systemctl start alldoing
sudo systemctl enable alldoing

echo "Checking health..."
curl -s http://localhost:8000/health && echo "" || echo "Health check failed — did you set REMOTE_LLM_API_KEY in .env?"
