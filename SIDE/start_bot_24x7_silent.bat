@echo off
REM Autostart / Task Scheduler uchun — pause yo'q. Qo'lda ishga tushirish uchun: start_bot_alohida_oyna.bat
cd /d "%~dp0"
start "ECOTIME-Bot" /MIN powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_24x7.ps1"
