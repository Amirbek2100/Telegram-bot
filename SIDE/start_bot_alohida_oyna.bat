@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Bot alohida PowerShell oynasida ishlaydi — Cursor yopsangiz ham bot ishda qoladi (shu oynani yopmang).
start "ECOTIME-Bot" /MIN powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_24x7.ps1"
echo.
echo Bot alohida (minimallashtirilgan) oynada ishga tushdi.
echo Oynani YOPMANG — yopsangiz bot ham toxtaydi.
echo Cursor ni yopishingiz mumkin.
echo.
pause
