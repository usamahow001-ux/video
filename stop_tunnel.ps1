# AI Shorts Generator - Stop the live tunnel (takes website offline)

$pidFile = Join-Path $PSScriptRoot "tunnel_pid.txt"

Write-Host "============================================="
Write-Host "  AI Shorts Generator - Stopping Tunnel"
Write-Host "============================================="

if (Test-Path $pidFile) {
    $pid = Get-Content $pidFile
    try {
        Stop-Process -Id $pid -Force -ErrorAction Stop
        Write-Host "Tunnel stopped (PID: $pid) - website is now offline."
    } catch {
        Write-Host "Tunnel was not running."
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
} else {
    Write-Host "No tunnel was running."
}

Read-Host "`nPress Enter to close"
