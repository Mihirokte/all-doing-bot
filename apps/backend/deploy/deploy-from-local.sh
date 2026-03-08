#!/usr/bin/env bash
# Deploy from your machine to EC2: sync repo and restart the backend service.
# Requires: EC2_HOST (or use EC2_INSTANCE_ID + AWS CLI to resolve), SSH key, and ssh/rsync.
#
# Usage:
#   EC2_HOST=ec2-1-2-3-4.compute-1.amazonaws.com ./deploy-from-local.sh
#   # or
#   EC2_INSTANCE_ID=i-xxxxx AWS_PROFILE=deploy-agent ./deploy-from-local.sh
#
# Optional env:
#   EC2_USER=ubuntu
#   REPO_DIR=/home/ubuntu/all-doing-bot
#   SERVICE_NAME=alldoing
#   SSH_KEY=path/to/key.pem

set -euo pipefail

EC2_USER="${EC2_USER:-ubuntu}"
REPO_DIR="${REPO_DIR:-/home/ubuntu/all-doing-bot}"
SERVICE_NAME="${SERVICE_NAME:-alldoing}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)

if [[ -n "${EC2_INSTANCE_ID:-}" && -z "${EC2_HOST:-}" ]]; then
  echo "[deploy] Resolving instance $EC2_INSTANCE_ID to public IP..."
  EC2_HOST=$(aws ec2 describe-instances \
    --instance-ids "$EC2_INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicDnsName' \
    --output text 2>/dev/null || true)
  if [[ -z "$EC2_HOST" || "$EC2_HOST" == "None" ]]; then
    echo "[deploy] Could not resolve EC2 host. Set EC2_HOST or check AWS credentials and instance ID."
    exit 1
  fi
fi

if [[ -z "${EC2_HOST:-}" ]]; then
  echo "[deploy] Set EC2_HOST or EC2_INSTANCE_ID (and AWS_PROFILE if needed)."
  exit 1
fi

TARGET="${EC2_USER}@${EC2_HOST}"
if [[ -n "${SSH_KEY:-}" ]]; then
  SSH_OPTS+=(-i "$SSH_KEY")
fi

echo "[deploy] Syncing repo to $TARGET..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# deploy/ is at apps/backend/deploy; repo root is three levels up
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
rsync -avz --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  --exclude '.git' \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude '.env' \
  --exclude '.pytest_cache' \
  "$REPO_ROOT/" "$TARGET:$REPO_DIR/"

echo "[deploy] Restarting $SERVICE_NAME on EC2..."
ssh "${SSH_OPTS[@]}" "$TARGET" "sudo systemctl restart $SERVICE_NAME"

echo "[deploy] Checking health..."
sleep 3
curl -sf --max-time 10 "http://${EC2_HOST}:8000/health" && echo "" || echo "[deploy] Health check failed or not reachable (check security group / port 8000)."

echo "[deploy] Done."
