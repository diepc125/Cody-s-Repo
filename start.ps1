# Sentinel — start backend + frontend (Ollama runs as a Windows background service)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Starting Sentinel..." -ForegroundColor Cyan

# ── Pre-flight: make sure Ollama is reachable for the Assistant tab ──
$ollamaModel = "qwen2.5:14b-instruct-q5_K_M"
try {
    $tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2
    Write-Host "  Ollama       -> OK" -ForegroundColor Green

    $hasModel = $tags.models | Where-Object { $_.name -eq $ollamaModel }
    if (-not $hasModel) {
        Write-Host "  Model        -> '$ollamaModel' not pulled yet" -ForegroundColor Yellow
        Write-Host "                  Run once: ollama pull $ollamaModel" -ForegroundColor Yellow
    } else {
        Write-Host "  Model        -> $ollamaModel ready" -ForegroundColor Green
    }
} catch {
    Write-Host "  Ollama       -> NOT RUNNING" -ForegroundColor Red
    Write-Host "                  The Assistant tab will not work until Ollama is installed." -ForegroundColor Yellow
    Write-Host "                  Install from https://ollama.com/download/windows" -ForegroundColor Yellow
}

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
Write-Host "  Ollama   -> http://localhost:11434 (background service)" -ForegroundColor Magenta
Write-Host "  Backend  -> http://localhost:8000" -ForegroundColor Green
Write-Host "  Frontend -> http://localhost:5173" -ForegroundColor Blue
Write-Host ""
Write-Host "Close the two new PowerShell windows to stop the app." -ForegroundColor Yellow
