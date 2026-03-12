#!/usr/bin/env bash
# Add 2 GB swap file on EC2. Run with sudo.
# Usage: sudo bash ec2-add-swap.sh

set -euo pipefail

SWAPFILE="${1:-/swapfile}"
SWAP_MB="${2:-2048}"

if [[ -f "$SWAPFILE" ]]; then
  echo "[swap] $SWAPFILE already exists. Current swap:"
  swapon --show
  exit 0
fi

echo "[swap] Creating ${SWAP_MB}MB swap file at $SWAPFILE..."
dd if=/dev/zero of="$SWAPFILE" bs=1M count="$SWAP_MB" status=progress
chmod 600 "$SWAPFILE"
mkswap "$SWAPFILE"
swapon "$SWAPFILE"
echo "$SWAPFILE none swap sw 0 0" >> /etc/fstab
echo "[swap] Done. Current swap:"
swapon --show
