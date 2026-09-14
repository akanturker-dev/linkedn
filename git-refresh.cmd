@echo off
cd /d "G:\Claude Projects\Asistanlar\linkedn"
powershell -NoProfile -ExecutionPolicy Bypass -File "git-refresh.ps1"
exit /b 0
