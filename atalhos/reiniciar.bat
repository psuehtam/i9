@echo off
title i9+ — reiniciar
setlocal
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\WindowsPowerShell\v1.0;%PATH%"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL%" set "POWERSHELL=%ProgramFiles%\PowerShell\7\pwsh.exe"
cd /d "%~dp0.."
echo Reiniciando o i9+ ...
"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 8000,3000; foreach ($port in $ports) { Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} } }"
"%SystemRoot%\System32\timeout.exe" /t 2 /nobreak >nul
echo.
echo Painel: http://localhost:3000
echo API:    http://127.0.0.1:8000/docs
echo Deixe esta janela aberta.
echo.
"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "scripts\start.ps1"
if errorlevel 1 pause
