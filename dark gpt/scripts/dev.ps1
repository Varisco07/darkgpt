<#
.SYNOPSIS
    Avvia DarkGPT (backend FastAPI e/o dashboard Next.js) su Windows/PowerShell.

.DESCRIPTION
    Usa `npm.cmd` invece di `npm`: su molte installazioni Windows la policy di
    esecuzione blocca `npm.ps1` con l'errore "L'esecuzione di script e'
    disabilitata nel sistema in uso". Passando dal wrapper `.cmd` il problema
    non si presenta e non serve modificare la policy globale della macchina.

.EXAMPLE
    .\scripts\dev.ps1
    .\scripts\dev.ps1 -Target backend
    .\scripts\dev.ps1 -Target frontend
#>

[CmdletBinding()]
param(
    [ValidateSet("all", "backend", "frontend")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
$frontend = Join-Path $repo "frontend"
$envFile = Join-Path $repo ".env"
$envExample = Join-Path $repo ".env.example"

if (-not (Test-Path $python)) {
    Write-Host "Ambiente virtuale non trovato: $python" -ForegroundColor Red
    Write-Host "Crealo con:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv"
    Write-Host "  & .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt"
    exit 1
}

if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "Creato .env da .env.example (configurazione predefinita)." -ForegroundColor Yellow
}

$backendArgs = @(
    "-m", "uvicorn", "app.main:app",
    "--app-dir", "backend",
    "--host", "127.0.0.1",
    "--port", "8000",
    "--reload"
)

function Start-Backend {
    Write-Host "Backend  -> http://127.0.0.1:8000" -ForegroundColor Cyan
    Push-Location $repo
    try {
        & $python @backendArgs
    }
    finally {
        Pop-Location
    }
}

function Start-Frontend {
    if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
        Write-Host "Dipendenze frontend mancanti, eseguo npm install..." -ForegroundColor Yellow
        Push-Location $frontend
        try { & npm.cmd install } finally { Pop-Location }
    }
    Write-Host "Dashboard -> http://localhost:3000" -ForegroundColor Cyan
    Push-Location $frontend
    try {
        & npm.cmd run dev
    }
    finally {
        Pop-Location
    }
}

switch ($Target) {
    "backend" { Start-Backend }
    "frontend" { Start-Frontend }
    default {
        # Due finestre separate: Ctrl+C in una non arresta l'altra.
        Write-Host "Avvio backend e dashboard in due finestre..." -ForegroundColor Cyan
        Start-Process powershell -ArgumentList @(
            "-NoExit", "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $PSScriptRoot "dev.ps1"), "-Target", "backend"
        )
        Start-Process powershell -ArgumentList @(
            "-NoExit", "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $PSScriptRoot "dev.ps1"), "-Target", "frontend"
        )
        Write-Host "Fatto. Chiudi le due finestre per arrestare i servizi." -ForegroundColor Green
    }
}
