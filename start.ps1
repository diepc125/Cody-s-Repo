# Sentinel — start backend + frontend in separate windows
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Starting Sentinel..." -ForegroundColor Cyan

# Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$root'; `
     Write-Host 'Backend starting...' -ForegroundColor Green; `
     python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000" `
    -WindowStyle Normal

Start-Sleep -Seconds 2

# Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$root\frontend'; `
     Write-Host 'Frontend starting...' -ForegroundColor Blue; `
     npm run dev" `
    -WindowStyle Normal

Write-Host ""
Write-Host "Sentinel is starting up:" -ForegroundColor Cyan
Write-Host "  Backend  -> http://localhost:8000" -ForegroundColor Green
Write-Host "  Frontend -> http://localhost:5173" -ForegroundColor Blue
Write-Host ""
Write-Host "Close the two new PowerShell windows to stop the app." -ForegroundColor Yellow
