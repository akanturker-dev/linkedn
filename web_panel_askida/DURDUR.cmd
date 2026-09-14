@echo off
chcp 65001 >nul
echo Web paneli durduruluyor...
taskkill /F /FI "WINDOWTITLE eq LinkedIn Asistan Sunucu*" >nul 2>&1
echo Durduruldu. Bu pencereyi kapatabilirsin.
pause
