<#
.SYNOPSIS
  Updates the production backend on EC2 over SSH (git pull main, pip, restart alldoing).

.DESCRIPTION
  Pipes ec2-pull-restart.sh to the remote shell so behavior matches .github/workflows/deploy-ec2.yml.
  Required: OpenSSH client (ssh). Optional: Git for Windows includes ssh.

  Environment (or pass parameters):
    EC2_HOST     — e.g. ec2-54-165-94-30.compute-1.amazonaws.com
    EC2_USER     — ubuntu or ec2-user (default: ubuntu)
    SSH_KEY      — path to .pem (optional if ssh uses your default key / ssh-agent)

.EXAMPLE
  $env:EC2_HOST = 'ec2-54-165-94-30.compute-1.amazonaws.com'
  $env:SSH_KEY = "$env:USERPROFILE\.ssh\alldoing_ec2"
  .\Invoke-Ec2BackendUpdate.ps1
#>
param(
    [string] $Ec2Host = $env:EC2_HOST,
    [string] $Ec2User = $(if ($env:EC2_USER) { $env:EC2_USER } else { "ubuntu" }),
    [string] $SshKey = $env:SSH_KEY
)

$ErrorActionPreference = "Stop"
if (-not $Ec2Host) {
    throw "Set EC2_HOST to your instance DNS or IP (see docs/deployment/ec2-runbook.md)."
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$remoteScript = Join-Path $here "ec2-pull-restart.sh"
if (-not (Test-Path $remoteScript)) {
    throw "Missing $remoteScript"
}

$target = "${Ec2User}@${Ec2Host}"
$sshArgs = @("-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15")
if ($SshKey) {
    $sshArgs += @("-i", $SshKey)
}

Write-Host '[deploy] SSH' $target '- running ec2-pull-restart.sh ...'
Get-Content -Raw -Encoding utf8 $remoteScript | & ssh @sshArgs $target "bash -s"
if ($LASTEXITCODE -ne 0) {
    throw "Remote update failed (exit $LASTEXITCODE)."
}
Write-Host '[deploy] Done.'
