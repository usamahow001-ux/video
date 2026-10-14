# ============================================
#  AI Shorts Generator - GO LIVE (website URL)
#  Makes http://localhost:8000 a real website
#  you can open from any device/browser
# ============================================

$cloudflared = "$env:USERPROFILE\Downloads\cloudflared.exe"
$pidFile = Join-Path $PSScriptRoot "tunnel_pid.txt"
$logFile = Join-Path $PSScriptRoot "tunnel_log.txt"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  AI Shorts Generator - Going LIVE!" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $cloudflared)) {
    Write-Host "[ERROR] cloudflared not found at $cloudflared" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Stop any old tunnel
if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile
    try {
        Stop-Process -Id $oldPid -Force -ErrorAction Stop
        Write-Host "Stopped old tunnel (PID: $oldPid)" -ForegroundColor Yellow
        Start-Sleep -Seconds 1
    } catch {
        Write-Host "Old tunnel not running" -ForegroundColor Yellow
    }
}

# Make sure the app server is up
$serverUp = Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue
if (-not $serverUp.TcpTestSucceeded) {
    Write-Host "`n[ERROR] App server is not running on localhost:8000" -ForegroundColor Red
    Write-Host "        Start it first with:  .\start_bg.ps1" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] App server detected on localhost:8000" -ForegroundColor Green

# Start cloudflared tunnel in background
$process = Start-Process -FilePath $cloudflared `
    -ArgumentList "tunnel --url http://localhost:8000 --no-autoupdate" `
    -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError "$logFile" `
    -PassThru

$process.Id | Out-File -FilePath $pidFile -Force

Write-Host "[START] Creating your website link..." -ForegroundColor Green

# Wait for the URL to appear in the log
$url = $null
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $logFile) {
        $match = Select-String -Path $logFile -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches | Select-Object -Last 1
        if ($match -and $match.Matches) {
            $url = $match.Matches[0].Value
            break
        }
    }
}

Write-Host ""
if ($url) {
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host "  YOUR WEBSITE IS LIVE!" -ForegroundColor Green
    Write-Host "  Open this link on ANY device:" -ForegroundColor Green
    Write-Host ""
    Write-Host "  $url" -ForegroundColor White -BackgroundColor DarkGreen
    Write-Host ""
    Write-Host "  Keep this PC on + tunnel running to stay online" -ForegroundColor Yellow
    Write-Host "  To stop the website, run:  .\stop_tunnel.ps1" -ForegroundColor Yellow
    Write-Host "=============================================" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Could not get the link. Check tunnel_log.txt" -ForegroundColor Red
    Get-Content $logFile -Tail 10
}

Read-Host "`nPress Enter to close this window (website keeps running)"
