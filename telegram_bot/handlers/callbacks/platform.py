from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.handlers.callbacks.terms import _proceed_after_platform


async def handle_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    platform = query.data.replace("PLATFORM:", "").upper()
    await _proceed_after_platform(query, context, platform)