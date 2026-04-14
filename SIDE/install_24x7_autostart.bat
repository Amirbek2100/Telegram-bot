@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ECOTIME bot — Windows ga kirganda avtomatik ishga tushish
echo Token: telegram_token.txt yoki bot.env shu papkada bo'lishi kerak.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_24x7_autostart.ps1"
if errorlevel 1 (
    echo.
    echo Agar xato bo'lsa: o'ng tugma - Run as administrator
    pause
    exit /b 1
)
echo.
pause
