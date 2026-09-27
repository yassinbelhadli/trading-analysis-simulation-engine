@echo off
cd /d "C:\Users\AGA GAMING\Desktop\test saas"
set PYTHONPATH=C:\Users\AGA GAMING\Desktop\test saas
start /B "" ".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, r'C:\Users\AGA GAMING\Desktop\test saas'); from telegram_bot.bot import TelegramApplication; TelegramApplication().run()" > bot_output.log 2> bot_error.log
echo Bot started in background (check bot_output.log / bot_error.log)
