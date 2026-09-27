from telegram import Update
from telegram.ext import ContextTypes

from core_engine.validation.harness import harness


async def validation_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report = harness.report()
    await update.message.reply_text(f"<pre>{report}</pre>", parse_mode="HTML")


async def validation_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = harness.tracker.summary()
    msg = (
        f"<b>Validation Summary</b>\n"
        f"Total: {summary['total']}\n"
        f"Complete: {summary['complete']}\n"
        f"Active: {summary['active']}\n"
        f"Failed: {summary['failed']}\n"
        f"Pending: {summary['pending']}\n"
        f"Success Rate: {summary['success_rate']}%"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
