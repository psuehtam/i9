@echo off
title i9+ — iniciar
setlocal
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\WindowsPowerShell\v1.0;%PATH%"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL%" set "POWERSHELL=%ProgramFiles%\PowerShell\7\pwsh.exe"
cd /d "%~dp0.."
echo Iniciando o i9+ ...
echo Painel: http://localhost:3000
echo API:    http://127.0.0.1:8000/docs
echo.
echo Deixe esta janela aberta. Feche-a ou use desligar.bat para parar.
echo.
"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "scripts\start.ps1"
if errorlevel 1 pause
