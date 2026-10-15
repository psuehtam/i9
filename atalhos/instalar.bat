@echo off
title NEXUS - Primeira instalacao
setlocal
cd /d "%~dp0.."
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\windows.ps1" -Action install
if errorlevel 1 pause
