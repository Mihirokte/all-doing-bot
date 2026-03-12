#!/usr/bin/env bash
# Run on EC2 after expanding the EBS volume in AWS (Console or CLI).
# Resizes the root partition and filesystem to use the new space.
# Usage: sudo bash ec2-expand-disk.sh

set -euo pipefail

ROOT_DEVICE="${1:-/dev/nvme0n1}"
ROOT_PARTITION="${2:-/dev/nvme0n1p1}"

echo "[expand-disk] Root device: $ROOT_DEVICE partition: $ROOT_PARTITION"

if ! command -v growpart &>/dev/null; then
  echo "[expand-disk] Installing cloud-utils-growpart..."
  dnf install -y cloud-utils-growpart 2>/dev/null || yum install -y cloud-utils-growpart
fi

echo "[expand-disk] Growing partition..."
growpart "$ROOT_DEVICE" 1 || true

echo "[expand-disk] Resizing filesystem..."
FS_TYPE=$(findmnt -n -o FSTYPE /)
case "$FS_TYPE" in
  xfs)
    xfs_growfs /
    ;;
  ext4|ext3)
    resize2fs "$ROOT_PARTITION"
    ;;
  *)
    echo "[expand-disk] Unknown FS type $FS_TYPE. Try: xfs_growfs / or resize2fs $ROOT_PARTITION"
    exit 1
    ;;
esac

echo "[expand-disk] Done. Current disk usage:"
df -h /
