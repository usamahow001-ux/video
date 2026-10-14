# AI Shorts Generator - Stop Background Server
$pidFile = Join-Path $PSScriptRoot "backend\server_pid.txt"

if (Test-Path $pidFile) {
    $pid = Get-Content $pidFile
    try {
        $proc = Get-Process -Id $pid -ErrorAction Stop
        Write-Host "Stopping server (PID: $pid)..."
        Stop-Process -Id $pid -Force
        Write-Host "Server stopped."
    } catch {
        Write-Host "Server (PID: $pid) is not running."
    }
    Remove-Item $pidFile -Force
} else {
    Write-Host "No server PID file found. Server may not be running."
}

# Also ensure anything listening on port 8000 is stopped
$port8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($port8000) {
    $ownerPid = $port8000.OwningProcess | Select-Object -First 1
    if ($ownerPid) {
        Write-Host "Stopping process on port 8000 (PID: $ownerPid)..."
        Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
    }
}
