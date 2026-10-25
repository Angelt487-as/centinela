@echo off
cd /d "%~dp0"

set "CENTINELA_ALLOWED_ORIGINS=https://gratuit-okay-flying-thanksgiving.trycloudflare.com"
set "CENTINELA_COOKIE_SECURE=1"

".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers

pause