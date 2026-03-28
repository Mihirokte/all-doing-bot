# Workflows

| File | Purpose |
|------|---------|
| `deploy-ec2.yml` | SSH to EC2: `git reset origin/main`, `pip install`, restart `alldoing`. Requires secrets `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`. Optional variable `EC2_AUTO_DEPLOY=true` for push-to-main deploy. |
| `deploy-pages.yml` | Deploy static frontend to `gh-pages` (if present in repo). |

Setup checklist for EC2: [docs/deployment/github-actions-ec2-autodeploy.txt](../../docs/deployment/github-actions-ec2-autodeploy.txt).
