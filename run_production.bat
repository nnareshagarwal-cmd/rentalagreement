@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM run_production.bat — Start AgreementAI with Gunicorn (production mode)
REM
REM Workers:     4  (adjust to 2 × CPU cores)
REM Worker type: gevent (async, handles 500 concurrent connections per worker)
REM Timeout:     30s (AI endpoints can be slow; set higher if needed)
REM Bind:        0.0.0.0:7000
REM
REM Total concurrent capacity: 4 workers × 500 connections = 2000 simultaneous
REM DB pool per worker: 20 connections → 4 × 20 = 80 total Postgres connections
REM ─────────────────────────────────────────────────────────────────────────

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
