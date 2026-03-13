# Expand EBS Volume on EC2

**Required for Ollama + Qwen3.5 and SearXNG.** The backend and `git pull` need free space; default root volume (8 GB) fills quickly. Use at least 20 GB.

## 1. Resize the volume in AWS

**Console:** EC2 → Volumes → select the volume attached to your instance → Actions → Modify volume → set size to 20 (or more) → Modify.

**CLI (with AWS credentials):**
```bash
VOLUME_ID=$(aws ec2 describe-instances --instance-ids i-08f6fa1828d35071e \
  --query "Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId" --output text --region us-east-1)
aws ec2 modify-volume --volume-id "$VOLUME_ID" --size 20 --region us-east-1
```

Wait a few minutes for the state to become `completed`.

## 2. Resize partition and filesystem on the instance

SSH into the instance, then:
```bash
sudo bash /home/ec2-user/all-doing-bot/apps/backend/deploy/ec2-expand-disk.sh
```

Or from the repo root:
```bash
sudo bash apps/backend/deploy/ec2-expand-disk.sh
```

Then run `df -h /` to confirm the root filesystem shows the new size.
