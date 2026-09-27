from __future__ import annotations
import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

from core_engine.simulation.planner import TradePlan
from core_engine.execution.broker import OrderResult
from core_engine.execution.errors import ExecutionError

logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_fill(self, plan: TradePlan, result: OrderResult,
                         chat_id: int):
        icon = "\U0001f7e2" if plan.side == "BUY" else "\U0001f534"
        lines = [
            f"\u2705 <b>Order Filled</b>",
            "",
            f"{icon} Symbol: <b>{plan.label or plan.side}</b>",
            f"\U0001f3ab Ticket: <code>{result.order_id}</code>",
        ]
        if result.filled_price:
            lines.append(f"\U0001f4b5 Entry: <b>{result.filled_price:.2f}</b>")
        if result.filled_volume:
            lines.append(f"\U0001f4e6 Lot: <b>{result.filled_volume:.2f}</b>")

        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text="\n".join(lines),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Failed to send fill message: %s", e)

    async def send_rejection(self, plan: TradePlan, error: ExecutionError,
                              chat_id: int):
        error_name = type(error).__name__
        lines = [
            f"\u274c <b>Order Rejected</b>",
            "",
            f"Symbol: <b>{plan.label or plan.side}</b>",
            f"\u26a0\ufe0f {error_name}: {error}",
        ]
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text="\n".join(lines),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Failed to send rejection message: %s", e)

    async def send_guard_block(self, symbol: str, direction: str,
                                reason: str, chat_id: int,
                                warnings: Optional[list] = None):
        lines = [
            f"\U0001f6ab <b>Trade Blocked</b>",
            "",
            f"Symbol: <b>{symbol}</b>",
            f"Direction: <b>{direction}</b>",
            f"\u26a0\ufe0f {reason}",
        ]
        if warnings:
            for w in warnings:
                lines.append(f"\u26a0 {w}")
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text="\n".join(lines),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Failed to send guard block: %s", e)
