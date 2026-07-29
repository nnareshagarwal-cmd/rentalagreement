@echo off
TITLE AgreementAI SaaS Platform - Port 7000
cd /d "%~dp0"

echo =========================================================
echo              AgreementAI SaaS Platform                   
echo       Server starting on: http://localhost:7000          
echo =========================================================
echo.
echo Press Ctrl+C in this window to stop the server.
echo.

python app.py

pause
