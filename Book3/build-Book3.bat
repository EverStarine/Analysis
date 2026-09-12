@echo off
chcp 936 > nul
title Analysis Book3 Build
"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-Book3.ps1" %*
set "BUILD_EXIT=%ERRORLEVEL%"
if /I "%~1"=="-NoPause" exit /b %BUILD_EXIT%
echo.
echo ExitCode=%BUILD_EXIT%
pause
exit /b %BUILD_EXIT%
