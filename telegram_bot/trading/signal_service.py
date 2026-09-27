from __future__ import annotations
import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

from core_engine.detection.setup_detector import SetupCandidate
from renderer_bridge import RenderService, setup_to_scene
from telegram_bot.ui.explainability import explain_snapshot, explain_trade_reasons

logger = logging.getLogger(__name__)


class SignalService:
    def __init__(self, bot: Bot, renderer: Optional[RenderService] = None):
        self.bot = bot
        self.renderer = renderer or RenderService()

    async def send_setup(self, candidate: SetupCandidate, chat_id: int):
        try:
            image = self.renderer.render_setup(candidate, minimal=True)
            caption = _format_setup_caption(candidate)
            await self.bot.send_photo(
                chat_id=chat_id,
                photo=image,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            logger.info("Signal sent: %s %s (score=%.0f)",
                         candidate.symbol, candidate.direction, candidate.score)
        except Exception as e:
            logger.error("Failed to send setup signal: %s", e)

    async def send_no_setup(self, symbol: str, timeframe: str,
                             chat_id: int, reason: str = ""):
        text = f"\u23f3 No ICT setup for {symbol} {timeframe}"
        if reason:
            text += f"\n<i>{reason}</i>"
        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            logger.error("Failed to send no-setup message: %s", e)


def _format_setup_caption(candidate: SetupCandidate) -> str:
    icon = "\U0001f534" if candidate.direction == "SELL" else "\U0001f7e2"
    lines = [
        f"{icon} <b>{candidate.direction} SIGNAL</b>",
        "",
        f"\U0001f4c8 Symbol: <b>{candidate.symbol}</b>",
        f"\u23f1 Timeframe: <b>{candidate.timeframe}</b>",
        f"\U0001f3af Score: <b>{candidate.score:.0f}/100</b>",
        f"\U0001f9e0 Confidence: <b>{candidate.confidence_score:.0f}%</b>",
    ]
    if candidate.session and candidate.session.current_session:
        lines.append(f"\U0001f3f0 Session: <b>{candidate.session.current_session.label}</b>")
    entry = _entry_price(candidate)
    has_levels = any([entry, candidate.stop_loss, candidate.take_profit])
    if has_levels:
        lines.append("")
        if entry:
            lines.append(f"\U0001f4b5 Entry: <b>{entry:.2f}</b>")
        if candidate.stop_loss:
            lines.append(f"\U0001f6a9 Stop Loss: <b>{candidate.stop_loss:.2f}</b>")
        if candidate.take_profit:
            lines.append(f"\U0001f3af TP: <b>{candidate.take_profit:.2f}</b>")

    if candidate.reasons:
        lines.append("")
        lines.append("\u2500" * 14)
        lines.append("<b>Why this trade?</b>")
        lines.append("")
        explanation = explain_trade_reasons(candidate.reasons, candidate.direction)
        for line in explanation.split("\n"):
            lines.append(f"\u2705 {line}")

    return "\n".join(lines)


def _entry_price(candidate: SetupCandidate) -> Optional[float]:
    if candidate.entry_zone:
        return candidate.entry_zone.get("entry_price")
    if candidate.ob and candidate.ob.ob_detected and candidate.ob.ob_mid:
        return candidate.ob.ob_mid
    if candidate.fvg and candidate.fvg.fvg_detected:
        if candidate.fvg.fvg_top and candidate.fvg.fvg_bottom:
            return (candidate.fvg.fvg_top + candidate.fvg.fvg_bottom) / 2
    return None
