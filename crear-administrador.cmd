@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ejecuta instalar.cmd antes de configurar el administrador.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\crear_administrador.py
pause
