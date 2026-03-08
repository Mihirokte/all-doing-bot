#!/usr/bin/env python3
"""
Create IAM user ai-agent-admin with EC2 permissions for the /aws skill.
Requires credentials with IAM create-user/policy/attach (e.g. default or admin profile).
Run: python setup_aws_iam_ai_agent.py
"""
from __future__ import annotations

import json
import os
import sys

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "boto3"])
    import boto3
    from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
AI_AGENT_USER = "ai-agent-admin"
AI_AGENT_POLICY = "AIAgentAdminEC2Policy"


def main() -> None:
    session = boto3.Session(region_name=REGION)
    sts = session.client("sts")
    iam = session.client("iam")

    try:
        identity = sts.get_caller_identity()
    except Exception as e:
        print("Cannot get caller identity. Set AWS credentials (e.g. default profile).", file=sys.stderr)
        raise SystemExit(1) from e

    account_id = identity["Account"]
    print(f"[setup] Account: {account_id} Region: {REGION}")

    policy_arn = f"arn:aws:iam::{account_id}:policy/{AI_AGENT_POLICY}"
    # EC2 only: full EC2 and related (VPC, security groups, key pairs) for instance management
    policy_doc = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "EC2Full",
                "Effect": "Allow",
                "Action": "ec2:*",
                "Resource": "*",
            },
        ],
    }

    try:
        iam.create_policy(PolicyName=AI_AGENT_POLICY, PolicyDocument=json.dumps(policy_doc))
        print(f"[setup] Created policy {AI_AGENT_POLICY}")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "EntityAlreadyExists":
            iam.create_policy_version(PolicyArn=policy_arn, PolicyDocument=json.dumps(policy_doc), SetAsDefault=True)
            print(f"[setup] Updated policy {AI_AGENT_POLICY}")
        else:
            raise

    try:
        iam.create_user(UserName=AI_AGENT_USER)
        print(f"[setup] Created user {AI_AGENT_USER}")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "EntityAlreadyExists":
            print(f"[setup] User {AI_AGENT_USER} already exists.")
        else:
            raise

    try:
        iam.attach_user_policy(UserName=AI_AGENT_USER, PolicyArn=policy_arn)
        print(f"[setup] Attached {AI_AGENT_POLICY} to {AI_AGENT_USER}")
    except ClientError:
        pass

    out = iam.create_access_key(UserName=AI_AGENT_USER)
    ak = out["AccessKey"]
    print()
    print("=== AI agent admin credentials (for /aws skill) ===")
    print("AccessKeyId:", ak["AccessKeyId"])
    print("SecretAccessKey:", ak["SecretAccessKey"])
    print("Profile name: ai-agent-admin")
    print()
    return ak["AccessKeyId"], ak["SecretAccessKey"]


if __name__ == "__main__":
    main()
