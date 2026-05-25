@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado.
  echo Execute primeiro: setup.ps1
  pause
  exit /b 1
)

echo Iniciando Domain Guard...
echo A janela do navegador sera aberta automaticamente.

start "Domain Guard - Servidor Local" cmd /k ".venv\Scripts\python.exe app.py"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5000"

exit /b 0
