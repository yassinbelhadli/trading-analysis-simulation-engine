from __future__ import annotations
import logging
from typing import List, Optional

from telegram import Bot
from telegram.constants import ParseMode

from core_engine.simulation.planner import TradePlan
from core_engine.simulation.result import TradeResult, TradeEvent, TradeState
from core_engine.simulation.lifecycle import TradeLifecycle
from core_engine.execution.broker import PositionInfo
from renderer_bridge import RenderService

logger = logging.getLogger(__name__)


class LifecycleService:
    def __init__(self, bot: Bot, renderer: Optional[RenderService] = None):
        self.bot = bot
        self.renderer = renderer or RenderService()

    async def send_tp_hit(self, ticket: str, tp_price: float,
                           position: PositionInfo, chat_id: int,
                           tp_number: int = 1):
        icon = "\U0001f7e2" if position.side.name == "BUY" else "\U0001f534"
        lines = [
            f"\U0001f3af <b>TP {tp_number} HIT</b>",
            "",
            f"Symbol: <b>{position.symbol}</b>",
            f"Price: <b>{tp_price:.2f}</b>",
        ]
        try:
            await self.bot.send_message(
                chat_id=chat_id, text="\n".join(lines),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Failed to send TP hit: %s", e)

    async def send_be_activated(self, ticket: str, be_price: float,
                                 position: PositionInfo, chat_id: int):
        lines = [
            f"\U0001f6e1 <b>Break Even Activated</b>",
            "",
            f"Symbol: <b>{position.symbol}</b>",
            f"SL moved to <b>{be_price:.2f}</b>",
            "",
            "\U0001f50d <i>Risk Free Trade</i>",
        ]
        try:
            await self.bot.send_message(
                chat_id=chat_id, text="\n".join(lines),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Failed to send BE: %s", e)

    async def send_trailing_activated(self, ticket: str,
                                       position: PositionInfo,
                                       chat_id: int):
        lines = [
            f"\U0001f3af <b>Trailing Activated</b>",
            "",
            f"Symbol: <b>{position.symbol}</b>",
            "Stop loss is now trailing",
        ]
        try:
            await self.bot.send_message(
                chat_id=chat_id, text="\n".join(lines),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Failed to send trailing: %s", e)

    async def send_trade_closed(
        self,
        result: TradeResult,
        plan: Optional[TradePlan] = None,
        candles: Optional[List] = None,
        chart_id: str = "",
        chat_id: int = 0,
    ):
        is_win = result.is_win
        is_loss = result.is_loss
        last = result.last_event

        exit_reason = "TP_HIT"
        if last:
            if TradeState.STOPPED in last.state:
                exit_reason = "SL_HIT"
            elif TradeState.CLOSED in last.state:
                exit_reason = "TP_HIT" if result.total_r > 0 else "MANUAL_CLOSE"

        if is_win and "TP" in exit_reason:
            header = f"\u2705 <b>Trade Closed</b>"
        elif is_loss or "SL" in exit_reason:
            header = f"\U0001f6ab <b>Trade Closed</b>"
        else:
            header = f"\U0001f4cc <b>Trade Closed</b>"

        icon = "\U0001f7e2" if is_win else "\U0001f534"
        pnl_sign = "+" if is_win else ""
        rr_label = f"{pnl_sign}{result.total_r:.2f}R" if result.total_r else ""
        reason_clean = exit_reason.replace("_", " ").title()

        lines = [
            header,
            "",
            f"{icon} Symbol: <b>{chart_id or ''}</b>",
            f"Reason: <b>{reason_clean}</b>",
            f"PnL: <b>{pnl_sign}${result.total_pnl:.2f}</b>",
        ]
        if rr_label:
            lines.append(f"Result: <b>{rr_label}</b>")

        if len(result.events) >= 2:
            first = result.events[0]
            last_ev = result.events[-1]
            if first.time and last_ev.time:
                lines.append(f"Duration: <b>{last_ev.time}</b>")

        if result.metrics:
            m = result.metrics
            if m.max_favorable_excursion:
                lines.append(f"MFE: <b>+{m.max_favorable_excursion:.2f}R</b>")
            if m.max_adverse_excursion:
                lines.append(f"MAE: <b>-{m.max_adverse_excursion:.2f}R</b>")

        text = "\n".join(lines)

        image = None
        if candles:
            try:
                image = self.renderer.render_trade(
                    result, candles, plan,
                    symbol=chart_id or "",
                    minimal=True,
                )
            except Exception as e:
                logger.warning("Failed to render trade chart: %s", e)

        try:
            if image:
                await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=image,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                )
            else:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
        except Exception as e:
            logger.error("Failed to send close notification: %s", e)
