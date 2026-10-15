@echo off
title NEXUS
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\windows.ps1" -Action start
if errorlevel 1 pause
