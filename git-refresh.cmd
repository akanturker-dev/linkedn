@echo off
REM 48-hour GitHub refresh: Check if 48 hours passed, auto-push if yes

cd /d "G:\Claude Projects\Asistanlar\linkedn"

REM Run PowerShell script silently
powershell -NoProfile -ExecutionPolicy Bypass -File "git-refresh.ps1"

exit /b 0
