#!/usr/bin/env bash
# From your laptop: SSH to EC2 and run the same update as GitHub Actions (git reset main, pip, systemd).
# Usage:
#   export EC2_HOST=ec2-54-165-94-30.compute-1.amazonaws.com
#   export EC2_USER=ubuntu   # or ec2-user
#   export SSH_KEY=~/.ssh/your.pem   # optional
#   ./ec2-ssh-pull-restart-from-local.sh
set -euo pipefail
EC2_USER="${EC2_USER:-ubuntu}"
if [[ -z "${EC2_HOST:-}" ]]; then
  echo "Set EC2_HOST (see apps/backend/deploy/ec2-runbook.md)." >&2
  exit 1
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${EC2_USER}@${EC2_HOST}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
[[ -n "${SSH_KEY:-}" ]] && SSH_OPTS+=(-i "$SSH_KEY")
echo "[deploy] ssh $TARGET < ec2-pull-restart.sh"
ssh "${SSH_OPTS[@]}" "$TARGET" "bash -s" <"$SCRIPT_DIR/ec2-pull-restart.sh"
echo "[deploy] Done."
