#!/usr/bin/env bash
# One-time IAM setup: creates DeployAgentPolicy, deploy-agent user, and EC2 role for SSM.
# Uses current AWS credentials (env or default profile). Run from repo root or apps/backend/deploy.
# Usage: AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=us-east-1 bash setup-aws-iam.sh
# Or: aws configure first, then bash setup-aws-iam.sh

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
DEPLOY_USER="deploy-agent"
DEPLOY_POLICY="DeployAgentPolicy"

echo "[setup-iam] Account: $ACCOUNT_ID Region: $REGION"

# 1. Create DeployAgentPolicy — EC2 describe only (free tier; no SSM/S3/other paid services)
echo "[setup-iam] Creating policy $DEPLOY_POLICY (EC2 describe only)..."
aws iam create-policy \
  --policy-name "$DEPLOY_POLICY" \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "DescribeEC2Only",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeTags"
      ],
      "Resource": "*"
    }]
  }' \
  2>/dev/null || aws iam get-policy --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/${DEPLOY_POLICY}" >/dev/null && echo "[setup-iam] Policy already exists."

POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${DEPLOY_POLICY}"

# 2. Create user deploy-agent
echo "[setup-iam] Creating user $DEPLOY_USER..."
aws iam create-user --user-name "$DEPLOY_USER" 2>/dev/null || echo "[setup-iam] User already exists."

# 3. Attach policy to user
echo "[setup-iam] Attaching policy to user..."
aws iam attach-user-policy --user-name "$DEPLOY_USER" --policy-arn "$POLICY_ARN" 2>/dev/null || true

# 4. Create access key for deploy-agent and output (user saves then deletes root keys)
echo "[setup-iam] Creating access key for $DEPLOY_USER..."
KEY_OUT=$(aws iam create-access-key --user-name "$DEPLOY_USER" 2>/dev/null) || true
if [[ -n "$KEY_OUT" ]]; then
  echo ""
  echo "=== SAVE THESE: deploy-agent credentials (then delete your root/current keys) ==="
  echo "$KEY_OUT" | python -c "
import sys, json
d = json.load(sys.stdin)['AccessKey']
print('AccessKeyId:', d['AccessKeyId'])
print('SecretAccessKey:', d['SecretAccessKey'])
" 2>/dev/null || echo "$KEY_OUT"
  echo "=== Add to ~/.aws/credentials as [deploy-agent] ==="
  echo ""
else
  echo "[setup-iam] User may already have 2 keys; create a new one in IAM console if needed."
fi

echo ""
echo "[setup-iam] Done. Summary (free tier only — EC2 describe, no paid services):"
echo "  - User: $DEPLOY_USER (policy: $DEPLOY_POLICY = ec2:Describe* only)"
echo "  - Deploy via SSH; no IAM role on EC2 = no other AWS service permissions."
echo "  - Region: $REGION"
