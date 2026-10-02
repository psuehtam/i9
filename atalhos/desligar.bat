@echo off
title i9+ — desligar
setlocal
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\WindowsPowerShell\v1.0;%PATH%"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL%" set "POWERSHELL=%ProgramFiles%\PowerShell\7\pwsh.exe"
cd /d "%~dp0.."
echo Encerrando o i9+ (portas 8000 e 3000)...
"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 8000,3000; foreach ($port in $ports) { Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction Stop; Write-Host ('Encerrado PID ' + $_.OwningProcess + ' na porta ' + $port) } catch {} } }; Write-Host 'Concluido.'"
echo.
pause
