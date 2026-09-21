@echo off
REM Windows equivalent of deploy/start.sh for local debugging.
REM Most production deploys will be Linux containers; this is here
REM so Windows users can try the same boot order.
setlocal

if not defined PORT set PORT=5000
if not defined API_PORT set API_PORT=8000
if not defined WORKERS set WORKERS=2

echo [jaguar] starting Flask GUI on 0.0.0.0:%PORT%
start "jaguar-flask" cmd /k gunicorn --bind 0.0.0.0:%PORT% --workers %WORKERS% --threads 2 --timeout 120 wsgi:app

echo [jaguar] starting FastAPI mobile API on 0.0.0.0:%API_PORT%
start "jaguar-api" cmd /k uvicorn --host 0.0.0.0 --port %API_PORT% api.mobile_api:app

echo [jaguar] both processes launched.
endlocal
