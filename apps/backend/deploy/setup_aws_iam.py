#!/usr/bin/env python3
"""
One-time IAM setup: deploy-agent user with EC2 describe-only (free tier).
No SSM, no S3, no other services — only read-only EC2 so you can find instance IP for SSH deploy.
Uses AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION (or default profile).
Run: python setup_aws_iam.py
"""
from __future__ import annotations

import json
import os
import sys

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Installing boto3...", file=sys.stderr)
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "boto3"])
    import boto3
    from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
DEPLOY_USER = "deploy-agent"
DEPLOY_POLICY = "DeployAgentPolicy"
# No EC2 instance role — free tier EC2 only; deploy via SSH (no SSM/permissions on instance).


def main() -> None:
    session = boto3.Session(region_name=REGION)
    sts = session.client("sts")
    iam = session.client("iam")

    try:
        identity = sts.get_caller_identity()
    except Exception as e:
        print("Cannot get caller identity. Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION.", file=sys.stderr)
        raise SystemExit(1) from e

    account_id = identity["Account"]
    print(f"[setup-iam] Account: {account_id} Region: {REGION}")

    policy_arn = f"arn:aws:iam::{account_id}:policy/{DEPLOY_POLICY}"
    # Free tier only: EC2 read-only describe (no charges). No SSM, S3, Lambda, RDS, etc.
    policy_doc = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DescribeEC2Only",
                "Effect": "Allow",
                "Action": [
                    "ec2:DescribeInstances",
                    "ec2:DescribeInstanceStatus",
                    "ec2:DescribeTags",
                ],
                "Resource": "*",
            },
        ],
    }

    # 1. Create policy or update to EC2-only (free tier)
    try:
        iam.create_policy(PolicyName=DEPLOY_POLICY, PolicyDocument=json.dumps(policy_doc))
        print(f"[setup-iam] Created policy {DEPLOY_POLICY} (EC2 describe only)")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "EntityAlreadyExists":
            iam.create_policy_version(PolicyArn=policy_arn, PolicyDocument=json.dumps(policy_doc), SetAsDefault=True)
            print(f"[setup-iam] Updated {DEPLOY_POLICY} to EC2 describe only (free tier).")
        else:
            raise

    # 2. Create user
    try:
        iam.create_user(UserName=DEPLOY_USER)
        print(f"[setup-iam] Created user {DEPLOY_USER}")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "EntityAlreadyExists":
            print(f"[setup-iam] User {DEPLOY_USER} already exists.")
        else:
            raise

    # 3. Attach policy to user
    try:
        iam.attach_user_policy(UserName=DEPLOY_USER, PolicyArn=policy_arn)
        print(f"[setup-iam] Attached {DEPLOY_POLICY} to {DEPLOY_USER}")
    except ClientError:
        pass

    # 4. Create access key
    try:
        keys = iam.list_access_keys(UserName=DEPLOY_USER)
        if len(keys.get("AccessKeyMetadata", [])) >= 2:
            print("[setup-iam] User already has 2 keys; create a new one in IAM console if needed.")
        else:
            out = iam.create_access_key(UserName=DEPLOY_USER)
            ak = out["AccessKey"]
            print()
            print("=== SAVE THESE: deploy-agent credentials (then delete your root/current keys) ===")
            print("AccessKeyId:", ak["AccessKeyId"])
            print("SecretAccessKey:", ak["SecretAccessKey"])
            print("=== Add to ~/.aws/credentials as [deploy-agent] ===")
            print()
    except ClientError as e:
        print("[setup-iam] Could not create access key:", e.response.get("Error", {}).get("Code", e))

    print()
    print("[setup-iam] Done. Summary (free tier only — EC2 describe, no paid services):")
    print(f"  - User: {DEPLOY_USER} (policy: {DEPLOY_POLICY} = ec2:Describe* only)")
    print(f"  - Deploy via SSH; no IAM role on EC2 = no other AWS service permissions.")
    print(f"  - Region: {REGION}")


if __name__ == "__main__":
    main()
