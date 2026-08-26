@echo off
TITLE AgreementAI SaaS Platform - Port 7000
cd /d "%~dp0"

echo =========================================================
echo              AgreementAI SaaS Platform                   
echo       Server starting on: http://localhost:7000          
echo       Workspace Path:     %CD%
echo =========================================================
echo.
echo Press Ctrl+C in this window to stop the server.
echo.

if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe app.py
) else (
  python app.py
)

pause
