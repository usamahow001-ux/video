# AI Shorts Generator - Start in Background
# Run this script ONCE, then close PowerShell and use the app in your browser

$backendDir = Join-Path $PSScriptRoot "backend"
$venvPython = Join-Path $backendDir "venv\Scripts\python.exe"
$appPy = Join-Path $backendDir "app.py"
$pidFile = Join-Path $backendDir "server_pid.txt"

Write-Host "============================================"
Write-Host "  AI Shorts Generator - Starting Background"
Write-Host "============================================"
Write-Host ""

# Kill any existing server first
if (Test-Path $pidFile) {
    $oldPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($oldPid) {
        try {
            $proc = Get-Process -Id $oldPid.Trim() -ErrorAction Stop
            Write-Host "Stopping old server (PID: $oldPid)..."
            Stop-Process -Id $oldPid.Trim() -Force
            Start-Sleep -Seconds 1
        } catch {
            Write-Host "Old server not running, starting fresh..."
        }
    }
}

# Also ensure port 8000 is free
$port8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($port8000) {
    $ownerPid = $port8000.OwningProcess | Select-Object -First 1
    if ($ownerPid) {
        Write-Host "Freeing port 8000 (PID: $ownerPid)..."
        Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

# Force UTF-8 so emoji in hooks/story text don't crash the server (Windows cp1252 default)
$env:PYTHONIOENCODING = "utf-8"

# Start server in background using Start-Process (no pipe deadlock issues)
$process = Start-Process -FilePath $venvPython `
    -ArgumentList "`"$appPy`"" `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden `
    -PassThru

# Save PID
$process.Id | Out-File -FilePath $pidFile -Force

Write-Host "Server started in background with PID: $($process.Id)"
Write-Host ""
Write-Host "Open http://localhost:8000 in your browser"
Write-Host ""
Write-Host "To stop the server later, run:"
Write-Host "  .\stop_bg.ps1"
Write-Host "============================================"

# Wait a moment and check it's running
Start-Sleep -Seconds 3
if (!$process.HasExited) {
    Write-Host "Server is running! (PID: $($process.Id))"
} else {
    Write-Host "Server failed to start. Try running manually to see errors:"
    Write-Host "  cd $backendDir"
    Write-Host "  .\venv\Scripts\Activate"
    Write-Host "  python app.py"
}

Read-Host "`nPress Enter to close this window (server keeps running in background)"
