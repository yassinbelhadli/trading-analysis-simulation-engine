from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Set

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from database.db import async_session_factory
from database.models import PaperTrade
from database.repositories import UserRepository
from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType
from renderer_bridge.render_service import RenderService
from telegram_bot.trading.signal_service import SignalService
from telegram_bot.trading.execution_service import ExecutionService
from telegram_bot.trading.lifecycle_service import LifecycleService
from telegram_bot.ui.explainability import (
    explain_snapshot_bullets,
    explain_snapshot,
    explain_trade_reasons,
)

logger = logging.getLogger(__name__)

EVENT_EMOJI: Dict[str, str] = {
    EventType.SETUP_DETECTED.value: "\U0001f534",
    EventType.PAPER_TRADE_PLANNED.value: "\U0001f7e2",
    EventType.TRADE_OPENED.value: "\u2705",
    EventType.TRADE_CLOSED.value: "\u2705",
    EventType.BREAK_EVEN_MOVED.value: "\U0001f6e1",
    EventType.PARTIAL_CLOSE.value: "\U0001f4cc",
    EventType.TRAILING_STOP_UPDATED.value: "\U0001f3af",
    EventType.TP_HIT.value: "\U0001f3af",
    EventType.SL_HIT.value: "\U0001f6ab",
    EventType.PAPER_TRADE_FILLED.value: "\u2705",
    EventType.PAPER_TRADE_TP_HIT.value: "\U0001f3af",
    EventType.PAPER_TRADE_SL_HIT.value: "\U0001f6ab",
    EventType.TRADE_BLOCKED.value: "\U0001f6ab",
    EventType.NEWS_UPDATED.value: "\u26a0\ufe0f",
    EventType.NEWS_COUNTDOWN.value: "\u23f3",
    EventType.ERROR.value: "\u274c",
    EventType.HEALTH_WARNING.value: "\u26a0\ufe0f",
    EventType.SYSTEM_INFO.value: "\u2139\ufe0f",
}

ALERT_EVENTS: Set[str] = {
    EventType.SETUP_DETECTED.value,
    EventType.PAPER_TRADE_PLANNED.value,
    EventType.TRADE_OPENED.value,
    EventType.TRADE_CLOSED.value,
    EventType.BREAK_EVEN_MOVED.value,
    EventType.PARTIAL_CLOSE.value,
    EventType.TRAILING_STOP_UPDATED.value,
    EventType.TP_HIT.value,
    EventType.SL_HIT.value,
    EventType.PAPER_TRADE_FILLED.value,
    EventType.PAPER_TRADE_TP_HIT.value,
    EventType.PAPER_TRADE_SL_HIT.value,
    EventType.TRADE_BLOCKED.value,
    EventType.NEWS_UPDATED.value,
    EventType.NEWS_COUNTDOWN.value,
    EventType.ERROR.value,
    EventType.HEALTH_WARNING.value,
    EventType.SYSTEM_INFO.value,
}


class AlertService:
    DEDUP_COOLDOWN = 1800

    def __init__(self, bot: Bot, renderer: Optional[RenderService] = None):
        self.bot = bot
        self.renderer = renderer or RenderService()
        self.signal_svc = SignalService(bot, self.renderer)
        self.exec_svc = ExecutionService(bot)
        self.lifecycle_svc = LifecycleService(bot, self.renderer)
        self._subscribed = False
        self._last_sent: Dict[str, float] = {}
        self._analysis_snapshots: Dict[str, dict] = {}

    def start(self):
        if self._subscribed:
            return
        for ev in ALERT_EVENTS:
            event_bus.subscribe(ev, self._on_event)
        self._subscribed = True
        logger.info("AlertService subscribed to %d event types", len(ALERT_EVENTS))

    def stop(self):
        if not self._subscribed:
            return
        for ev in ALERT_EVENTS:
            event_bus.unsubscribe(ev, self._on_event)
        self._subscribed = False

    def _on_event(self, data: dict):
        import asyncio
        asyncio.create_task(self._dispatch(data))

    async def _dispatch(self, data: dict):
        user_id = data.get("user_id", "")
        chat_id = await self._get_telegram_chat(user_id)
        if not chat_id:
            return

        event_type = data.get("event_type", "")
        payload = data.get("data", {})
        message = data.get("message", "")

        try:
            if event_type == EventType.SETUP_DETECTED.value:
                if not self._should_send(payload):
                    return
                await self._send_signal(payload, chat_id)

            elif event_type == EventType.PAPER_TRADE_PLANNED.value:
                if not self._should_send(payload):
                    return
                await self._send_signal(payload, chat_id)

            elif event_type in (EventType.TRADE_OPENED.value,
                                EventType.PAPER_TRADE_FILLED.value):
                await self._handle_fill(payload, chat_id)

            elif event_type in (EventType.TP_HIT.value,
                                EventType.PAPER_TRADE_TP_HIT.value):
                await self._handle_tp_hit(payload, chat_id)

            elif event_type in (EventType.SL_HIT.value,
                                EventType.PAPER_TRADE_SL_HIT.value):
                await self._handle_sl_hit(payload, chat_id)

            elif event_type == EventType.BREAK_EVEN_MOVED.value:
                await self._handle_be(payload, chat_id)

            elif event_type == EventType.TRAILING_STOP_UPDATED.value:
                await self._handle_trailing(payload, chat_id)

            elif event_type in (EventType.TRADE_CLOSED.value,
                                EventType.PARTIAL_CLOSE.value):
                await self._handle_close(payload, chat_id)

            elif event_type == EventType.TRADE_BLOCKED.value:
                await self.exec_svc.send_guard_block(
                    payload.get("symbol", ""),
                    payload.get("direction", ""),
                    message or payload.get("reason", ""),
                    chat_id,
                    payload.get("warnings"),
                )

            elif event_type == EventType.NEWS_UPDATED.value:
                await self._handle_news_event(payload, chat_id)

            elif event_type == EventType.NEWS_COUNTDOWN.value:
                await self._handle_news_countdown(payload, chat_id)

            elif event_type in (EventType.ERROR.value,
                                EventType.HEALTH_WARNING.value):
                await self._send_simple(chat_id, event_type, message)

            elif event_type == EventType.SYSTEM_INFO.value:
                await self._send_simple(chat_id, event_type, message)

        except Exception as e:
            logger.error("Alert dispatch failed for %s: %s", event_type, e)

    def _should_send(self, payload: dict) -> bool:
        symbol = payload.get("symbol", "")
        direction = payload.get("direction", "")
        key = f"{symbol}:{direction}"
        now = time.time()
        last = self._last_sent.get(key, 0)
        if now - last < self.DEDUP_COOLDOWN:
            logger.info("Dedup skipped: %s (%.0fs remaining)",
                        key, self.DEDUP_COOLDOWN - (now - last))
            return False
        self._last_sent[key] = now
        return True

    # ── Signal (SETUP_DETECTED / PAPER_TRADE_PLANNED) ────────────

    async def _send_signal(self, payload: dict, chat_id: int):
        """Send professional trade signal with chart + explainability."""
        symbol = payload.get("symbol", "")
        direction = payload.get("direction", "")
        score = payload.get("score", 0)
        confidence = payload.get("confidence", 0)
        entry = _get(payload, "entry_price")
        sl = _get(payload, "stop_loss")
        tp = _get(payload, "take_profit")
        rr = float(payload.get("risk_reward", 0))
        lot = float(payload.get("lot_size", 0))
        timeframe = payload.get("timeframe", payload.get("market_regime", "M5"))
        session = payload.get("session", "")
        snapshot = payload.get("snapshot")
        if not snapshot:
            logger.warning("Signal has no snapshot -> text-only fallback: %s %s",
                           symbol, direction)
        score_val = float(score) if score else 0
        conf_val = float(confidence) if confidence else 0

        icon = "\U0001f534" if direction == "SELL" else "\U0001f7e2"
        header = f"{icon} <b>{direction} {symbol}</b>"
        if timeframe:
            header += f"  <i>({timeframe})</i>"

        lines = [header, ""]
        lines.append(f"\U0001f3af Score: <b>{score_val:.0f}/100</b>")
        lines.append(f"\U0001f9e0 Confidence: <b>{conf_val:.0f}%</b>")
        if session:
            lines.append(f"\U0001f3f0 Session: <b>{session}</b>")

        has_levels = any([entry, sl, tp, rr, lot])
        if has_levels:
            lines.append("")
            if entry:
                lines.append(f"\U0001f4b5 Entry: <b>{entry:.2f}</b>")
            if sl:
                lines.append(f"\U0001f6a9 SL: <b>{sl:.2f}</b>")
            if tp:
                lines.append(f"\U0001f3af TP: <b>{tp:.2f}</b>")
            if rr:
                lines.append(f"\U0001f4ca Risk/Reward: <b>{rr:.1f}R</b>")
            if lot:
                lines.append(f"\U0001f4e6 Lot: <b>{lot:.2f}</b>")

        # Explainability — compact checklist in the caption
        bullets = explain_snapshot_bullets(snapshot) if snapshot else []
        reasons = (payload.get("reasons")
                   or ((snapshot or {}).get("scoring", {}) or {}).get("reasons")
                   or [])
        if not bullets and reasons:
            bullets = explain_trade_reasons(reasons, direction).split("\n")
        if bullets:
            lines.append("")
            lines.append("<b>Why this trade?</b>")
            for b in bullets:
                lines.append(f"\u2705 {b}")

        text = "\n".join(lines)

        # Render chart from snapshot
        image_bytes = None
        if snapshot:
            try:
                pil_image = self.renderer.render_snapshot(snapshot, minimal=True)
                image_bytes = self.renderer.to_bytes(pil_image)
            except Exception as e:
                logger.warning("Failed to render signal chart: %s", e)

        reply_markup = None
        if snapshot:
            key = self._store_analysis_snapshot(snapshot, payload)
            if key:
                reply_markup = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "\U0001f50d View Analysis", callback_data=f"ANALYSIS:{key}"),
                ]])

        try:
            if image_bytes:
                await self.bot.send_photo(
                    chat_id=chat_id, photo=image_bytes,
                    caption=text, parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
                logger.info("Signal sent with chart: %s %s (score=%.0f)", symbol, direction, score_val)
            else:
                await self._send_text(chat_id, text)
        except Exception as e:
            logger.error("Failed to send signal: %s", e)

    def _store_analysis_snapshot(self, snapshot: dict, payload: dict) -> Optional[str]:
        """Keep the snapshot for the 'View Analysis' callback (bounded LRU)."""
        try:
            key = str(payload.get("candidate_id")
                      or payload.get("setup_id")
                      or (snapshot.get("metadata", {}) or {}).get("setup_id")
                      or f"{payload.get('symbol','')}:{int(time.time())}")
        except Exception:
            key = f"{payload.get('symbol', 'x')}:{int(time.time())}"
        if not key or len(key) > 64:
            key = f"{payload.get('symbol', 'x')}:{int(time.time())}"
        self._analysis_snapshots[key] = snapshot
        if len(self._analysis_snapshots) > 50:
            oldest = next(iter(self._analysis_snapshots))
            self._analysis_snapshots.pop(oldest, None)
        return key

    def get_analysis_snapshot(self, key: str) -> Optional[dict]:
        """Retrieve a stored snapshot for the 'View Analysis' callback."""
        return self._analysis_snapshots.get(key)

    # ── Fill ─────────────────────────────────────────────────────

    async def _handle_fill(self, payload: dict, chat_id: int):
        ticket = payload.get("ticket") or payload.get("order_id", "")
        price = _get(payload, "filled_price") or _get(payload, "entry") or _get(payload, "price", 0)
        symbol = payload.get("symbol", "")
        side = payload.get("side", payload.get("direction", "BUY"))
        lot = float(payload.get("lot_size", 0))
        sl = _get(payload, "sl")
        tp = _get(payload, "tp")

        icon = "\U0001f7e2" if side == "BUY" else "\U0001f534"
        lines = [
            f"\u2705 <b>Order Filled</b>",
            "",
            f"{icon} Symbol: <b>{symbol}</b>",
            f"\U0001f3ab Ticket: <code>{ticket}</code>",
        ]
        if price:
            lines.append(f"\U0001f4b5 Entry: <b>{price:.2f}</b>")
        if lot:
            lines.append(f"\U0001f4e6 Lot: <b>{lot:.2f}</b>")
        if sl:
            lines.append(f"\U0001f6a9 SL: <b>{sl:.2f}</b>")
        if tp:
            lines.append(f"\U0001f3af TP: <b>{tp:.2f}</b>")

        text = "\n".join(lines)

        # Filled Trade Chart — uses the REAL execution price from MT5
        image_bytes = None
        snapshot = payload.get("snapshot")
        if snapshot:
            try:
                snap = dict(snapshot)
                drawing = dict(snap.get("drawing", {}) or {})
                if price:
                    drawing["entry_price"] = float(price)
                if sl is not None:
                    drawing["sl_price"] = float(sl)
                if tp is not None:
                    drawing["tp"] = [float(tp)]
                snap["drawing"] = drawing
                pil_image = self.renderer.render_snapshot(snap, minimal=True)
                image_bytes = self.renderer.to_bytes(pil_image)
            except Exception as e:
                logger.warning("Failed to render filled chart: %s", e)

        try:
            if image_bytes:
                await self.bot.send_photo(
                    chat_id=chat_id, photo=image_bytes,
                    caption=text, parse_mode=ParseMode.HTML,
                )
            else:
                await self._send_text(chat_id, text)
        except Exception as e:
            logger.error("Failed to send fill: %s", e)

    # ── TP Hit ───────────────────────────────────────────────────

    async def _handle_tp_hit(self, payload: dict, chat_id: int):
        tp_num = payload.get("tp_number", 1)
        price = _get(payload, "price") or _get(payload, "exit_price")
        symbol = payload.get("symbol", "")
        pnl = _get(payload, "realized_pnl")

        lines = [
            f"\U0001f3af <b>TP {tp_num} HIT</b>",
            "",
            f"Symbol: <b>{symbol}</b>",
        ]
        if price:
            lines.append(f"Price: <b>{price:.2f}</b>")
        if pnl is not None:
            pnl_val = float(pnl)
            sign = "+" if pnl_val >= 0 else ""
            lines.append(f"Profit: <b>{sign}${pnl_val:.2f}</b>")

        await self._send_text(chat_id, "\n".join(lines))

    # ── SL Hit ───────────────────────────────────────────────────

    async def _handle_sl_hit(self, payload: dict, chat_id: int):
        price = _get(payload, "price") or _get(payload, "exit_price")
        symbol = payload.get("symbol", "")
        pnl = _get(payload, "realized_pnl")

        lines = [
            f"\U0001f6ab <b>SL HIT</b>",
            "",
            f"Symbol: <b>{symbol}</b>",
        ]
        if price:
            lines.append(f"Price: <b>{price:.2f}</b>")
        if pnl is not None:
            pnl_val = float(pnl)
            sign = "+" if pnl_val >= 0 else ""
            lines.append(f"Loss: <b>{sign}${pnl_val:.2f}</b>")

        await self._send_text(chat_id, "\n".join(lines))

    # ── Break Even ───────────────────────────────────────────────

    async def _handle_be(self, payload: dict, chat_id: int):
        price = payload.get("breakeven_price", payload.get("price", 0))
        symbol = payload.get("symbol", "")
        lines = [
            f"\U0001f6e1 <b>Break Even Activated</b>",
            "",
            f"Symbol: <b>{symbol}</b>",
        ]
        if price:
            lines.append(f"SL moved to <b>{price:.2f}</b>")
        else:
            lines.append("SL moved to Entry")
        lines.append("")
        lines.append("\U0001f50d <i>Risk Free Trade</i>")
        await self._send_text(chat_id, "\n".join(lines))

    # ── Trailing Stop ────────────────────────────────────────────

    async def _handle_trailing(self, payload: dict, chat_id: int):
        symbol = payload.get("symbol", "")
        lines = [
            f"\U0001f3af <b>Trailing Activated</b>",
            "",
            f"Symbol: <b>{symbol}</b>",
            "Stop loss is now trailing",
        ]
        await self._send_text(chat_id, "\n".join(lines))

    # ── Close / Partial Close ───────────────────────────────────

    async def _handle_close(self, payload: dict, chat_id: int):
        symbol = payload.get("symbol", "")
        pnl = float(payload.get("realized_pnl", payload.get("pnl", 0)))
        r = float(payload.get("realized_r", payload.get("r_multiple", 0)))
        is_partial = payload.get("event_type", "") == EventType.PARTIAL_CLOSE.value
        exit_reason = payload.get("exit_reason", payload.get("reason", ""))
        duration = payload.get("duration", "")
        mfe = _get(payload, "mfe")
        mae = _get(payload, "mae")
        remaining = _get(payload, "remaining_pct")

        is_win = pnl >= 0
        pnl_sign = "+" if is_win else ""

        if is_partial:
            header = f"\U0001f4cc <b>Partial Close</b>"
        elif is_win:
            header = f"\u2705 <b>Trade Closed</b>"
        else:
            header = f"\U0001f6ab <b>Trade Closed</b>"

        lines = [header, ""]
        lines.append(f"Symbol: <b>{symbol}</b>")

        if exit_reason:
            reason_clean = exit_reason.replace("_", " ").title()
            lines.append(f"Reason: <b>{reason_clean}</b>")

        lines.append(f"PnL: <b>{pnl_sign}${pnl:.2f}</b>")
        if r:
            lines.append(f"Result: <b>{pnl_sign}{r:.2f}R</b>")
        if duration:
            lines.append(f"Duration: <b>{duration}</b>")
        if mfe is not None:
            lines.append(f"MFE: <b>+{float(mfe):.2f}R</b>")
        if mae is not None:
            lines.append(f"MAE: <b>-{float(mae):.2f}R</b>")
        if remaining is not None:
            lines.append(f"Remaining: <b>{remaining}</b>")

        await self._send_text(chat_id, "\n".join(lines))

    # ── News ────────────────────────────────────────────────────

    async def _handle_news_event(self, payload: dict, chat_id: int):
        event_name = payload.get("event", payload.get("name", "Economic Event"))
        currency = payload.get("currency", "USD")
        impact = payload.get("impact", "MEDIUM")
        forecast = payload.get("forecast", "")
        previous = payload.get("previous", "")
        event_time = payload.get("time", "")

        impact_icon = "\U0001f534" if impact == "HIGH" else "\U0001f7e0"
        lines = [
            f"\u26a0\ufe0f <b>Upcoming {impact} Impact Event</b>\n",
            f"{impact_icon} <b>{event_name}</b>",
            f"\U0001f4c5 {event_time}",
            f"\U0001f4b1 {currency}",
        ]
        if forecast:
            lines.append(f"\U0001f4ca Forecast: {forecast}")
        if previous:
            lines.append(f"\U0001f4c8 Previous: {previous}")
        lines.append("\n\u23f3 Trading will be blocked 30min before this event.")
        await self._send_text(chat_id, "\n".join(lines))

    async def _handle_news_countdown(self, payload: dict, chat_id: int):
        event_name = payload.get("event", "Event")
        minutes = payload.get("minutes_remaining", 0)
        impact = payload.get("impact", "HIGH")

        if minutes <= 0:
            lines = [
                f"\U0001f534 <b>LIVE</b>\n",
                f"\U0001f534 <b>{event_name}</b> is now releasing.",
                f"Trading paused until volatility subsides.",
            ]
        else:
            lines = [
                f"\u23f3 <b>{minutes} min</b>\n",
                f"\U0001f534 {event_name} starts in <b>{minutes} minutes</b>.",
                f"High market volatility expected.",
            ]
        await self._send_text(chat_id, "\n".join(lines))

    # ── Simple ──────────────────────────────────────────────────

    async def _send_simple(self, chat_id: int, event_type: str, message: str):
        icon_map = {
            EventType.ERROR.value: "\u274c",
            EventType.HEALTH_WARNING.value: "\u26a0\ufe0f",
            EventType.SYSTEM_INFO.value: "\u2139\ufe0f",
        }
        icon = icon_map.get(event_type, "\u2139\ufe0f")
        text = f"{icon} {message}"
        await self._send_text(chat_id, text)

    async def _send_text(self, chat_id: int, text: str):
        try:
            await self.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Failed to send message to %s: %s", chat_id, e)

    async def _get_telegram_chat(self, user_id: str) -> Optional[int]:
        if not user_id:
            return None
        try:
            async with async_session_factory() as session:
                repo = UserRepository(session)
                user = await repo.get_by_id(user_id)
                if user and user.telegram_id:
                    return int(user.telegram_id)
        except Exception as e:
            logger.warning("Failed to resolve telegram ID for %s: %s", user_id, e)
        return None


def _get(d: dict, *keys) -> Any:
    for k in keys:
        val = d.get(k)
        if val is not None:
            return val
    return None
