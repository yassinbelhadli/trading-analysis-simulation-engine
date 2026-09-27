from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.ui.trade_messages import format_help

logger = logging.getLogger(__name__)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_help())
