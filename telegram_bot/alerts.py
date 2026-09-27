# telegram_bot/alerts.py
from typing import Optional

from telegram_bot.bot import TelegramBot, TelegramResult
from monitoring.logs.notifications import Notification


class TelegramAlerts:
    def __init__(
        self,
        bot: Optional[TelegramBot] = None,
    ):
        self.bot = bot or TelegramBot()

    def send_notification(
        self,
        notification: Notification,
    ) -> TelegramResult:

        text = self._format_notification(notification)

        return self.bot.send_message(text)

    def _format_notification(
        self,
        notification: Notification,
    ) -> str:

        emoji = self._level_emoji(notification.level)

        payload = notification.payload or {}

        symbol = payload.get("symbol") or payload.get("normalized_symbol") or ""
        direction = payload.get("direction", "")
        lot_size = payload.get("lot_size", "")
        entry_price = payload.get("entry_price", "")
        stop_loss = payload.get("stop_loss", "")
        take_profit = payload.get("take_profit", "")
        pnl_money = payload.get("pnl_money", "")
        pnl_points = payload.get("pnl_points", "")

        lines = [
            f"{emoji} <b>{notification.event_type}</b>",
            "",
            f"<b>Trade ID:</b> {notification.trade_id}",
            f"<b>Message:</b> {notification.message}",
        ]

        if symbol:
            lines.append(f"<b>Symbol:</b> {symbol}")

        if direction:
            lines.append(f"<b>Direction:</b> {direction}")

        if lot_size != "":
            lines.append(f"<b>Lot:</b> {lot_size}")

        if entry_price != "":
            lines.append(f"<b>Entry:</b> {entry_price}")

        if stop_loss != "":
            lines.append(f"<b>SL:</b> {stop_loss}")

        if take_profit != "":
            lines.append(f"<b>TP:</b> {take_profit}")

        if pnl_points != "":
            lines.append(f"<b>PNL Points:</b> {pnl_points}")

        if pnl_money != "":
            lines.append(f"<b>PNL Money:</b> {pnl_money}")

        lines.append("")
        lines.append(f"<b>Level:</b> {notification.level}")

        return "\n".join(lines)

    def _level_emoji(self, level: str) -> str:
        mapping = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨",
        }

        return mapping.get(level, "ℹ️")