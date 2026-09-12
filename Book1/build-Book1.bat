@echo off
chcp 936 > nul
title Analysis Book1 Build
"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-Book1.ps1"
echo.
echo ExitCode=%ERRORLEVEL%
pause
