from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.handlers.callbacks.menu import handle_my_accounts

# Legacy handler — redirects to new menu handler
async def handle_my_accounts_legacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_my_accounts(update, context)
