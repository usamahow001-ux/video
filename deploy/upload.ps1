<#
  AI Shorts Generator - Upload to Oracle Cloud VM (run from Windows)

  Packages the project (skipping your local venv, uploads, output and the
  Windows FFmpeg binaries) and copies it to the VM, then optionally runs the
  server setup for you.

  Usage:
    powershell -ExecutionPolicy Bypass -File deploy\upload.ps1 `
        -Server 123.45.67.89 -Key C:\path\to\ssh-key.key

    # ...and run the server setup automatically afterwards:
    powershell -ExecutionPolicy Bypass -File deploy\upload.ps1 `
        -Server 123.45.67.89 -Key C:\path\to\ssh-key.key -RunSetup
#>
param(
    [Parameter(Mandatory = $true)][string]$Server,   # VM public IP
    [Parameter(Mandatory = $true)][string]$Key,      # path to your SSH private key
    [string]$UserName = "ubuntu",                    # Ubuntu images use "ubuntu"
    [switch]$RunSetup
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot          # ...\shorts-generator
$projectParent = Split-Path -Parent $root         # folder that CONTAINS shorts-generator
$target = "$UserName@$Server"
$tarball = Join-Path $env:TEMP "shorts-generator.tar.gz"
$sshOpts = @("-i", $Key, "-o", "StrictHostKeyChecking=accept-new")

Write-Host "Packaging project (excluding venv / uploads / output / ffmpeg_bin)..." -ForegroundColor Cyan
Push-Location $projectParent
tar --exclude='shorts-generator/backend/venv' `
    --exclude='shorts-generator/backend/uploads' `
    --exclude='shorts-generator/backend/output' `
    --exclude='shorts-generator/backend/ffmpeg_bin' `
    --exclude='shorts-generator/backend/__pycache__' `
    --exclude='shorts-generator/backend/services/__pycache__' `
    --exclude='shorts-generator/backend/database.db' `
    -czf $tarball shorts-generator
Pop-Location

Write-Host "Uploading to $target ..." -ForegroundColor Cyan
scp @sshOpts $tarball "${target}:~/shorts-generator.tar.gz"

Write-Host "Extracting on the server..." -ForegroundColor Cyan
ssh @sshOpts $target "tar -xzf ~/shorts-generator.tar.gz -C ~ && rm -f ~/shorts-generator.tar.gz"

if ($RunSetup) {
    Write-Host "Running server setup (ffmpeg + deps + systemd service)..." -ForegroundColor Cyan
    ssh @sshOpts $target "bash ~/shorts-generator/deploy/setup_server.sh"
}

Write-Host ""
Write-Host "Done. Project is at ~/shorts-generator on the server." -ForegroundColor Green
if (-not $RunSetup) {
    Write-Host "Next: ssh -i `"$Key`" $target" -ForegroundColor Yellow
    Write-Host "      bash ~/shorts-generator/deploy/setup_server.sh" -ForegroundColor Yellow
}
