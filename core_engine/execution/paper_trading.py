from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.db import async_session_factory
from database.models import PaperTrade
from core_engine.detection.setup_detector import SetupCandidate
from core_engine.execution.trade_planner import TradePlan

logger = logging.getLogger(__name__)


def _inject_risk_percent(snapshot: dict, plan: "TradePlan") -> dict:
    """Inject risk_percent and other plan-time data into snapshot drawing."""
    drawing = snapshot.setdefault("drawing", {})
    if plan.risk_percent is not None:
        drawing["risk_percent"] = plan.risk_percent
    drawing["lot_size"] = plan.lot_size
    drawing["risk_reward"] = plan.risk_reward
    return snapshot


class PaperTradingService:

    @staticmethod
    async def create_from_plan(
        account_id: str,
        user_id: str,
        candidate: SetupCandidate,
        plan: TradePlan,
        session_name: Optional[str] = None,
        market_regime: Optional[str] = None,
        candidate_id: Optional[str] = None,
    ) -> PaperTrade:
        async with async_session_factory() as s:
            trade = PaperTrade(
                account_id=account_id,
                user_id=user_id,
                symbol=plan.symbol,
                direction=plan.direction,
                entry_price=plan.entry_price,
                stop_loss=plan.stop_loss,
                take_profit=plan.take_profit,
                risk_reward=plan.risk_reward,
                lot_size=plan.lot_size,
                risk_percent=plan.risk_percent,
                score=candidate.score,
                confidence=candidate.confidence_score,
                rank=candidate.rank,
                status="PLANNED",
                reasons=",".join(candidate.reasons) if candidate.reasons else None,
                session=session_name,
                market_regime=market_regime,
                candidate_id=candidate_id,
                snapshot=_inject_risk_percent(candidate.to_snapshot(), plan),
            )
            s.add(trade)
            await s.commit()
            await s.refresh(trade)
            logger.info("Paper trade saved: %s %s %s @ %.2f session=%s",
                        trade.symbol, trade.direction, trade.id, trade.entry_price, session_name)
            return trade

    @staticmethod
    async def has_active_trade(account_id: str, symbol: str, direction: str) -> bool:
        async with async_session_factory() as session:
            from sqlalchemy import select
            stmt = select(PaperTrade).where(
                PaperTrade.account_id == account_id,
                PaperTrade.symbol == symbol,
                PaperTrade.direction == direction,
                PaperTrade.status != "CLOSED",
            ).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    @staticmethod
    def get_snapshot(trade: PaperTrade) -> Optional[dict]:
        """Return the trading snapshot dict from a PaperTrade."""
        return trade.snapshot if trade.snapshot else None

    @staticmethod
    async def close_stale_planned_trades(minutes: int = 15) -> int:
        from datetime import timedelta
        from sqlalchemy import select, update
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        async with async_session_factory() as s:
            stmt = (
                select(PaperTrade.id)
                .where(
                    PaperTrade.status == "PLANNED",
                    PaperTrade.created_at < cutoff,
                )
            )
            result = await s.execute(stmt)
            ids = [row[0] for row in result.fetchall()]
            if ids:
                upd = (
                    update(PaperTrade)
                    .where(PaperTrade.id.in_(ids))
                    .values(
                        status="CLOSED",
                        close_reason="STALE_CLEANUP",
                        executed_at=datetime.now(timezone.utc),
                    )
                )
                await s.execute(upd)
                await s.commit()
                logger.info("Closed %d stale PLANNED trades (>=%d min old)", len(ids), minutes)
            return len(ids)

    @staticmethod
    def build_plan_data(trade: PaperTrade, plan: TradePlan) -> dict:
        return {
            "id": trade.id,
            "symbol": plan.symbol,
            "direction": plan.direction,
            "entry_price": plan.entry_price,
            "stop_loss": plan.stop_loss,
            "take_profit": plan.take_profit,
            "risk_reward": plan.risk_reward,
            "lot_size": plan.lot_size,
            "risk_percent": plan.risk_percent,
            "score": trade.score,
            "confidence": trade.confidence,
            "rank": trade.rank,
            "reasons": trade.reasons.split(",") if trade.reasons else [],
            "session": trade.session,
            "market_regime": trade.market_regime,
            "candidate_id": trade.candidate_id,
        }


paper_trading = PaperTradingService()
