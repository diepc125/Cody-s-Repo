# Sentinel — pull latest, then start backend + frontend in separate windows
$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$branch = "claude/trading-algorithm-McKTc"

Write-Host "Sentinel" -ForegroundColor Cyan
Write-Host "--------"

# Pull latest from remote
Set-Location $root
Write-Host "Pulling latest from $branch..." -ForegroundColor Yellow
git pull origin $branch
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "git pull failed. Resolve the issue above, then run start.ps1 again." -ForegroundColor Red
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# Show what we're on
$commit = git log -1 --oneline
Write-Host "At commit: $commit" -ForegroundColor DarkGray
Write-Host ""

# Backend
Write-Host "Starting backend on http://localhost:8000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$root'; `
     Write-Host 'Backend' -ForegroundColor Green; `
     python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000" `
    -WindowStyle Normal

Start-Sleep -Seconds 2

# Frontend
Write-Host "Starting frontend on http://localhost:5173" -ForegroundColor Blue
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$root\frontend'; `
     Write-Host 'Frontend' -ForegroundColor Blue; `
     npm run dev" `
    -WindowStyle Normal

Write-Host ""
Write-Host "Both servers starting. Close their windows to stop." -ForegroundColor DarkGray
