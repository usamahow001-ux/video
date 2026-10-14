<#
  AI Shorts Generator - Deploy to Hugging Face Spaces (runs 24/7 free)
  Usage:
    powershell -ExecutionPolicy Bypass -File .\deploy_hf.ps1 -SpaceUrl "https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME" -Token "hf_YourWriteTokenHere"
#>
param(
    [Parameter(Mandatory = $false)][string]$SpaceUrl,
    [Parameter(Mandatory = $false)][string]$Token
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Deploy to Hugging Face Spaces (24/7 Free)  " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

if (-not $SpaceUrl) {
    $SpaceUrl = Read-Host "Paste your Hugging Face Space URL (e.g. https://huggingface.co/spaces/username/myspace)"
}
$SpaceUrl = $SpaceUrl.Trim().TrimEnd("/")

if (-not $SpaceUrl -or $SpaceUrl -notmatch "huggingface\.co/spaces/([^/]+)/([^/]+)") {
    Write-Host "[ERROR] Invalid Hugging Face Space URL. Format: https://huggingface.co/spaces/username/space-name" -ForegroundColor Red
    exit 1
}

$hfUser = $Matches[1]
$hfSpace = $Matches[2]

if (-not $Token) {
    Write-Host "Tip: Create a WRITE token at: https://huggingface.co/settings/tokens" -ForegroundColor Yellow
    $Token = Read-Host "Paste your Hugging Face Access Token (hf_...)"
}
$Token = $Token.Trim()

# Form authenticated remote URL
$pushUrl = "https://${hfUser}:${Token}@huggingface.co/spaces/${hfUser}/${hfSpace}.git"
$displayUrl = "https://huggingface.co/spaces/${hfUser}/${hfSpace}"
$directAppUrl = "https://${hfUser}-${hfSpace}.hf.space"

Push-Location $root

try {
    # 1. Initialize git if not already
    if (-not (Test-Path ".git")) {
        Write-Host "[1/5] Initializing local git repository..." -ForegroundColor Cyan
        git init -b main
    } else {
        Write-Host "[1/5] Git repository already initialized." -ForegroundColor Cyan
        git branch -M main 2>$null
    }

    # Set dummy user name/email if not configured
    $hasName = git config user.name
    if (-not $hasName) {
        git config user.name "Shorts Generator"
        git config user.email "shorts@local"
    }

    # 2. Configure remote
    Write-Host "[2/5] Configuring Hugging Face remote..." -ForegroundColor Cyan
    $existingRemote = git remote get-url origin 2>$null
    if ($existingRemote) {
        git remote set-url origin $pushUrl
    } else {
        git remote add origin $pushUrl
    }

    # 3. Stage files
    Write-Host "[3/5] Staging files (excluding temporary data & logs)..." -ForegroundColor Cyan
    git add Dockerfile .dockerignore README.md backend frontend deploy_hf.ps1 .gitignore

    # 4. Commit
    Write-Host "[4/5] Committing changes..." -ForegroundColor Cyan
    git commit -m "Deploy AI Shorts Generator to Hugging Face Spaces" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "No changes to commit, continuing..." -ForegroundColor Gray
    }

    # 5. Push to Hugging Face
    Write-Host "[5/5] Pushing to Hugging Face Spaces..." -ForegroundColor Cyan
    git push --force origin main

    Write-Host ""
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host "  SUCCESSFULLY DEPLOYED TO HUGGING FACE!" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  1. Space Dashboard (view build status):" -ForegroundColor Cyan
    Write-Host "     $displayUrl" -ForegroundColor White
    Write-Host ""
    Write-Host "  2. Direct Web App URL (works on any device):" -ForegroundColor Cyan
    Write-Host "     $directAppUrl" -ForegroundColor White
    Write-Host ""
    Write-Host "  Note: Hugging Face will take 2-3 minutes to build" -ForegroundColor Yellow
    Write-Host "  the Docker container on first launch." -ForegroundColor Yellow
    Write-Host "=============================================" -ForegroundColor Green
} finally {
    Pop-Location
}
