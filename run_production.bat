@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM run_production.bat — Start AgreementAI with Gunicorn (production mode)
REM ─────────────────────────────────────────────────────────────────────────
cd /d "%~dp0"

echo =========================================================
echo              AgreementAI SaaS Platform (Production)      
echo       Server starting on: http://0.0.0.0:7000            
echo       Workspace Path:     %CD%
echo =========================================================
echo.

set FLASK_DEBUG=False
set FLASK_ENV=production

gunicorn ^
  --workers 4 ^
  --worker-class gevent ^
  --worker-connections 500 ^
  --bind 0.0.0.0:7000 ^
  --timeout 30 ^
  --access-logfile - ^
  --error-logfile - ^
  app:app
