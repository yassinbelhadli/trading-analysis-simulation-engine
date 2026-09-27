@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%
start "" /B ".venv\Scripts\python.exe" scripts/live_feed.py > live_feed_output.log 2> live_feed_error.log
echo Live Feed started in background. PID: %ERRORLEVEL%
