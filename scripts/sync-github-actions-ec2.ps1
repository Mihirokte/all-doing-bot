<#
.SYNOPSIS
  Push EC2 SSH credentials to GitHub Actions secrets (and optional auto-deploy variable).

.DESCRIPTION
  Uses GitHub CLI (`gh`). Run once: `gh auth login` with scopes including `repo` and `workflow`.
  Run from repo root. Does not print secret values.

.PARAMETER Ec2Host
  Instance DNS or IP (default: this project's public DNS).

.PARAMETER Ec2User
  SSH login (ec2-user on Amazon Linux, ubuntu on Ubuntu AMIs).

.PARAMETER PrivateKeyPath
  Path to OpenSSH private key (no .pub).

.PARAMETER SkipAutoDeployVariable
  If set, do not create/update EC2_AUTO_DEPLOY (otherwise sets it to true).

.EXAMPLE
  .\scripts\sync-github-actions-ec2.ps1
.EXAMPLE
  .\scripts\sync-github-actions-ec2.ps1 -Ec2Host "ec2-1-2-3.compute-1.amazonaws.com" -Ec2User "ubuntu" -PrivateKeyPath "$env:USERPROFILE\.ssh\id_ed25519"
#>
param(
    [string] $Ec2Host = "ec2-54-165-94-30.compute-1.amazonaws.com",
    [string] $Ec2User = "ec2-user",
    [string] $PrivateKeyPath = "$env:USERPROFILE\.ssh\alldoing_ec2",
    [switch] $SkipAutoDeployVariable
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "Install GitHub CLI: https://cli.github.com/ then run gh auth login"
}

gh auth status 2>&1 | Out-Host
if (-not (Test-Path -LiteralPath $PrivateKeyPath)) {
    throw "Private key not found: $PrivateKeyPath"
}

Write-Host "[gh] Setting repository secrets (values hidden)..."
gh secret set EC2_HOST --body $Ec2Host
gh secret set EC2_USER --body $Ec2User
Get-Content -Raw -Encoding utf8 $PrivateKeyPath | gh secret set EC2_SSH_KEY

if (-not $SkipAutoDeployVariable) {
    Write-Host "[gh] Setting EC2_AUTO_DEPLOY repository variable to true..."
    gh variable set EC2_AUTO_DEPLOY --body "true"
}

Write-Host "[gh] Done. Verify: gh secret list && gh variable list"
Write-Host "Workflow: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions/workflows/deploy-ec2.yml"
