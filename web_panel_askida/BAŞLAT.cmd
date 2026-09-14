@echo off
chcp 65001 >nul
setlocal
rem Web paneli askida: masaustu uygulamasi aciksa bu panel acilmaz (ayni anda tek asistan calisir)
cd /d "%~dp0.."

powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient).Connect('127.0.0.1',8877); exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
    echo Web paneli zaten calisiyor, tarayicida aciliyor...
    start "" "http://127.0.0.1:8877"
    goto :eof
)

where python >nul 2>&1
if errorlevel 1 (
    echo HATA: Python bulunamadi.
    pause
    exit /b 1
)

if not exist venv (
    python -m venv venv
)

"venv\Scripts\python.exe" -m pip install -q --only-binary=:all: -r requirements.txt
"venv\Scripts\python.exe" -m playwright install chromium

start "LinkedIn Asistan Sunucu" /min "venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8877

timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:8877"

echo.
echo Web paneli calisiyor. Durdurmak icin bu klasordeki DURDUR.cmd dosyasini calistir.
pause
