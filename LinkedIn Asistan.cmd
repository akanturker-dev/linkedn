@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo HATA: Python bulunamadi.
    echo https://www.python.org/downloads/ adresinden Python 3.9 veya ustunu kur, kurulumda "Add to PATH" kutusunu isaretle.
    pause
    exit /b 1
)

if not exist "venv\Scripts\pythonw.exe" (
    echo Ilk kurulum yapiliyor, sanal ortam olusturuluyor...
    python -m venv venv || goto :hata
)

rem Paketler sadece requirements.txt degistiyse yeniden kurulur, yoksa uygulama hemen acilir
fc /b requirements.txt "venv\kurulu_gereksinimler.txt" >nul 2>&1
if errorlevel 1 (
    echo Gerekli paketler kuruluyor, ilk seferde birkac dakika surebilir...
    "venv\Scripts\python.exe" -m pip install -q -U pip || goto :hata
    "venv\Scripts\python.exe" -m pip install -q --only-binary=:all: -r requirements.txt || goto :hata
    echo Yedek tarayici bileseni kontrol ediliyor...
    "venv\Scripts\python.exe" -m playwright install chromium || goto :hata
    copy /y requirements.txt "venv\kurulu_gereksinimler.txt" >nul
)

start "" "venv\Scripts\pythonw.exe" masaustu.py
exit /b 0

:hata
echo.
echo Kurulum sirasinda bir hata oldu. Bu pencerenin ekran goruntusunu Claude'a gonder.
pause
exit /b 1
