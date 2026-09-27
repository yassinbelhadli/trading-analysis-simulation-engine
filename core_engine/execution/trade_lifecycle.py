from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update

from database.db import async_session_factory
from database.models import PaperTrade
from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType

logger = logging.getLogger(__name__)

BE_ACTIVATION_PCT = 0.5
PARTIAL_RR_TRIGGER = 1.0
PARTIAL_CLOSE_PCT = 0.5


class TradeLifecycleManager:
    ALLOWED_TRANSITIONS = {
        "PLANNED": ["FILLED"],
        "FILLED": ["CLOSED"],
    }

    @staticmethod
    async def get_active_trades(account_id: str) -> List[PaperTrade]:
        async with async_session_factory() as s:
            stmt = (
                select(PaperTrade)
                .where(
                    PaperTrade.account_id == account_id,
                    PaperTrade.status.in_(["PLANNED", "FILLED"]),
                )
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    @staticmethod
    async def fill_trade(trade_id: str, fill_price: float) -> Optional[PaperTrade]:
        async with async_session_factory() as s:
            result = await s.execute(select(PaperTrade).where(PaperTrade.id == trade_id))
            trade = result.scalar_one_or_none()
            if not trade:
                logger.warning("Trade %s not found for fill", trade_id)
                return None
            if trade.status != "PLANNED":
                logger.warning("Trade %s cannot fill: status=%s", trade_id, trade.status)
                return None
            trade.status = "FILLED"
            trade.executed_at = datetime.now(timezone.utc)
            trade.fill_latency_sec = round((trade.executed_at - trade.created_at).total_seconds(), 1)
            trade.highest_price = fill_price
            trade.lowest_price = fill_price
            risk_distance = abs(trade.entry_price - trade.stop_loss)
            trade.initial_risk_usd = round(risk_distance * trade.lot_size, 2)
            trade.validation_batch = 2
            await s.commit()
            await s.refresh(trade)
            logger.info(
                "Trade FILLED: %s %s @ %.2f fill_latency=%.1fs",
                trade.symbol, trade.direction, fill_price, trade.fill_latency_sec or 0,
            )
            return trade

    @staticmethod
    async def hit_tp(trade_id: str, exit_price: float) -> Optional[PaperTrade]:
        return await TradeLifecycleManager._close_trade(
            trade_id, exit_price, "CLOSED", reason_label="TP_HIT",
        )

    @staticmethod
    async def hit_sl(trade_id: str, exit_price: float) -> Optional[PaperTrade]:
        return await TradeLifecycleManager._close_trade(
            trade_id, exit_price, "CLOSED", reason_label="SL_HIT",
        )

    @staticmethod
    async def track_price(trade_id: str, current_price: float) -> None:
        async with async_session_factory() as s:
            result = await s.execute(
                select(
                    PaperTrade.highest_price,
                    PaperTrade.lowest_price,
                    PaperTrade.partial_closed,
                    PaperTrade.post_partial_highest_price,
                    PaperTrade.post_partial_lowest_price,
                )
                .where(PaperTrade.id == trade_id)
            )
            row = result.one_or_none()
            if not row:
                return
            high, low, p_closed, pp_high, pp_low = row
            new_high = current_price if high is None else max(high, current_price)
            new_low = current_price if low is None else min(low, current_price)
            updates: dict = {}
            if new_high != high or new_low != low:
                updates["highest_price"] = new_high
                updates["lowest_price"] = new_low
            if p_closed:
                new_pp_high = current_price if pp_high is None else max(pp_high, current_price)
                new_pp_low = current_price if pp_low is None else min(pp_low, current_price)
                if new_pp_high != pp_high or new_pp_low != pp_low:
                    updates["post_partial_highest_price"] = new_pp_high
                    updates["post_partial_lowest_price"] = new_pp_low
            if updates:
                stmt = (
                    update(PaperTrade)
                    .where(PaperTrade.id == trade_id)
                    .values(**updates)
                )
                await s.execute(stmt)
                await s.commit()

    @staticmethod
    def _current_rr(trade: PaperTrade, current_price: float) -> float:
        if trade.stop_loss == trade.entry_price:
            return 0.0
        if trade.direction == "BUY":
            risk = trade.entry_price - trade.stop_loss
            if risk <= 0:
                return 0.0
            return (current_price - trade.entry_price) / risk
        risk = trade.stop_loss - trade.entry_price
        if risk <= 0:
            return 0.0
        return (trade.entry_price - current_price) / risk

    @staticmethod
    def check_partial_trigger(trade: PaperTrade, current_price: float) -> bool:
        if trade.partial_closed or trade.status != "FILLED":
            return False
        return TradeLifecycleManager._current_rr(trade, current_price) >= PARTIAL_RR_TRIGGER

    @staticmethod
    async def execute_partial_close(trade_id: str, current_price: float) -> Optional[PaperTrade]:
        async with async_session_factory() as s:
            result = await s.execute(select(PaperTrade).where(PaperTrade.id == trade_id))
            trade = result.scalar_one_or_none()
            if not trade or trade.partial_closed:
                return None
            portion_pnl = TradeLifecycleManager._calc_pnl(trade, current_price) * PARTIAL_CLOSE_PCT
            trade.partial_closed = True
            trade.partial_price = current_price
            trade.partial_pnl = round(portion_pnl, 2)
            trade.post_partial_highest_price = current_price
            trade.post_partial_lowest_price = current_price
            trade.lot_size = round(trade.lot_size * (1.0 - PARTIAL_CLOSE_PCT), 4)
            trade.breakeven_activated = True
            trade.breakeven_price = trade.entry_price
            trade.stop_loss = trade.entry_price
            await s.commit()
            await s.refresh(trade)
            logger.info(
                "Trade %s: %s %s partial @ %.2f pnl=%.2f remaining_lot=%.4f",
                trade.id[:8], trade.symbol, trade.direction,
                current_price, trade.partial_pnl, trade.lot_size,
            )
            return trade

    @staticmethod
    async def _close_trade(
        trade_id: str,
        exit_price: float,
        close_reason: str,
        reason_label: str,
    ) -> Optional[PaperTrade]:
        async with async_session_factory() as s:
            result = await s.execute(select(PaperTrade).where(PaperTrade.id == trade_id))
            trade = result.scalar_one_or_none()
            if not trade:
                logger.warning("Trade %s not found for %s", trade_id, reason_label)
                return None
            if trade.status != "FILLED":
                logger.warning("Trade %s cannot close: status=%s", trade_id, trade.status)
                return None
            trade.mfe = TradeLifecycleManager._calc_mfe(trade)
            trade.mae = TradeLifecycleManager._calc_mae(trade)
            trade.status = close_reason
            trade.exit_price = exit_price
            trade.close_reason = reason_label
            remaining_pnl = TradeLifecycleManager._calc_pnl(trade, exit_price)
            if trade.partial_closed and trade.partial_pnl is not None:
                trade.realized_pnl = round(trade.partial_pnl + remaining_pnl, 2)
                trade.runner_mfe = TradeLifecycleManager._calc_runner_mfe(trade)
                trade.runner_efficiency = TradeLifecycleManager._calc_runner_efficiency(trade)
            else:
                trade.realized_pnl = remaining_pnl
            if trade.initial_risk_usd and trade.initial_risk_usd > 0:
                trade.realized_r = round(trade.realized_pnl / trade.initial_risk_usd, 2)
            trade.closed_at = datetime.now(timezone.utc)
            if trade.executed_at:
                trade.trade_duration_sec = round(
                    (trade.closed_at - trade.executed_at).total_seconds(), 1,
                )
            await s.commit()
            await s.refresh(trade)
            pnl_note = f" partial={trade.partial_pnl}" if trade.partial_closed else ""
            logger.info(
                "Trade %s: %s %s exit=%.2f pnl=%.2f reason=%s "
                "duration=%.1fs MFE=%.2f MAE=%.2f%s",
                trade.id[:8], trade.symbol, trade.direction,
                exit_price, trade.realized_pnl, reason_label,
                trade.trade_duration_sec or 0,
                trade.mfe or 0, trade.mae or 0, pnl_note,
            )
            return trade

    @staticmethod
    def _calc_mfe(trade: PaperTrade) -> Optional[float]:
        if trade.direction == "BUY":
            if trade.highest_price is None:
                return None
            return round(max(0.0, trade.highest_price - trade.entry_price), 2)
        if trade.lowest_price is None:
            return None
        return round(max(0.0, trade.entry_price - trade.lowest_price), 2)

    @staticmethod
    def _calc_mae(trade: PaperTrade) -> Optional[float]:
        if trade.direction == "BUY":
            if trade.lowest_price is None:
                return None
            return round(max(0.0, trade.entry_price - trade.lowest_price), 2)
        if trade.highest_price is None:
            return None
        return round(max(0.0, trade.highest_price - trade.entry_price), 2)

    @staticmethod
    def _calc_runner_mfe(trade: PaperTrade) -> Optional[float]:
        if trade.partial_price is None:
            return None
        if trade.direction == "BUY":
            if trade.post_partial_highest_price is None:
                return None
            return round(max(0.0, trade.post_partial_highest_price - trade.partial_price), 2)
        if trade.post_partial_lowest_price is None:
            return None
        return round(max(0.0, trade.partial_price - trade.post_partial_lowest_price), 2)

    @staticmethod
    def _calc_runner_efficiency(trade: PaperTrade) -> Optional[float]:
        if trade.runner_mfe is None or trade.partial_pnl is None or trade.partial_price is None:
            return None
        # Runner PnL from partial_price to exit, using remaining lot
        remaining_lot = trade.lot_size
        if trade.direction.upper() in ("BUY", "LONG"):
            runner_pnl = (trade.exit_price - trade.partial_price) * remaining_lot
        else:
            runner_pnl = (trade.partial_price - trade.exit_price) * remaining_lot
        max_opp = trade.runner_mfe * remaining_lot
        if max_opp <= 0:
            return 0.0
        return round(runner_pnl / max_opp, 4)

    @staticmethod
    def _calc_pnl(trade: PaperTrade, exit_price: float) -> float:
        diff = exit_price - trade.entry_price
        if trade.direction == "SELL":
            diff = -diff
        return round(diff * trade.lot_size, 2)

    @staticmethod
    def check_fill(trade: PaperTrade, current_price: float) -> bool:
        if trade.direction == "BUY":
            return current_price >= trade.entry_price
        return current_price <= trade.entry_price

    @staticmethod
    def check_tp(trade: PaperTrade, current_price: float) -> bool:
        if trade.direction == "BUY":
            return current_price >= trade.take_profit
        return current_price <= trade.take_profit

    @staticmethod
    def check_sl(trade: PaperTrade, current_price: float) -> bool:
        effective_sl = trade.breakeven_price if trade.breakeven_activated else trade.stop_loss
        if trade.direction == "BUY":
            return current_price <= effective_sl
        return current_price >= effective_sl

    @staticmethod
    def check_be_activation(trade: PaperTrade, current_price: float) -> bool:
        if trade.breakeven_activated or trade.status != "FILLED":
            return False
        if trade.direction == "BUY":
            move_pct = (current_price - trade.entry_price) / trade.entry_price * 100
        else:
            move_pct = (trade.entry_price - current_price) / trade.entry_price * 100
        return move_pct >= BE_ACTIVATION_PCT

    @staticmethod
    async def activate_breakeven(trade_id: str) -> Optional[PaperTrade]:
        async with async_session_factory() as s:
            result = await s.execute(select(PaperTrade).where(PaperTrade.id == trade_id))
            trade = result.scalar_one_or_none()
            if not trade or trade.breakeven_activated:
                return None
            trade.breakeven_activated = True
            trade.breakeven_price = trade.entry_price
            trade.stop_loss = trade.entry_price
            await s.commit()
            await s.refresh(trade)
            logger.info(
                "Trade %s: %s %s BE activated SL=%.2f",
                trade.id[:8], trade.symbol, trade.direction, trade.breakeven_price,
            )
            return trade


trade_lifecycle = TradeLifecycleManager()
