@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONPATH=%CD%
set TF_CPP_MIN_LOG_LEVEL=3
start "" /B ".venv\Scripts\python.exe" telegram_bot/bot.py
echo Bot started.
timeout /t 2 /nobreak >nul
exit
