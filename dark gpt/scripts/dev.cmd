@echo off
rem Avvia backend e dashboard in due finestre separate.
setlocal
start "DarkGPT backend" cmd /k call "%~dp0dev-backend.cmd"
start "DarkGPT frontend" cmd /k call "%~dp0dev-frontend.cmd"
echo Backend:  http://127.0.0.1:8000
echo Dashboard: http://localhost:3000
