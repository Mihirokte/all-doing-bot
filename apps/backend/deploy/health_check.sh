#!/usr/bin/env bash
# Run from cron every 5 min: curl -sf http://localhost:8000/health || systemctl restart alldoing
# Usage: ./health_check.sh [base_url]
BASE_URL="${1:-http://localhost:8000}"
if ! curl -sf --max-time 10 "${BASE_URL}/health" > /dev/null; then
  echo "Health check failed for ${BASE_URL}; restarting alldoing"
  systemctl restart alldoing
fi
