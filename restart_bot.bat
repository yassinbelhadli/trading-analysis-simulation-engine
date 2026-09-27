@echo off
chcp 65001 >nul
echo Stopping bot...
taskkill /f /im python.exe >nul 2>&1
timeout /t 3 /nobreak >nul
echo Starting bot...
cd /d "%~dp0"
set PYTHONPATH=%CD%
set TF_CPP_MIN_LOG_LEVEL=3
start "" /B ".venv\Scripts\python.exe" telegram_bot/bot.py
echo Bot restarted successfully.
timeout /t 2 /nobreak >nul
exit
