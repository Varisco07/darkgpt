@echo off
rem Avvia la dashboard DarkGPT su http://localhost:3000 (cmd/PowerShell).
setlocal
cd /d "%~dp0..\frontend"

if not exist "node_modules" (
    echo Dipendenze frontend mancanti, eseguo npm install...
    call npm.cmd install
    if errorlevel 1 exit /b 1
)

call npm.cmd run dev
