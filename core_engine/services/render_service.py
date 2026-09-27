from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from database.db import async_session_factory
from database.models import PaperTrade

logger = logging.getLogger(__name__)


class RenderService:
    """Single entry point for generating trade images from snapshots.

    Every visual output (Telegram, Dashboard, Reports) goes through here.
    No calculations — only reads snapshot data and passes it to the renderer.
    """

    @staticmethod
    async def render_entry(trade_id: str) -> Optional[str]:
        """Generate entry chart from a trade's snapshot."""
        snapshot = await RenderService._load_snapshot(trade_id)
        if not snapshot:
            return None
        return RenderService._render(trade_id, snapshot)

    @staticmethod
    async def render_exit(trade_id: str, exit_price: float, realized_pnl: float,
                          realized_r: float, mfe: Optional[float] = None,
                          mae: Optional[float] = None,
                          be_price: Optional[float] = None) -> Optional[str]:
        """Generate exit chart by augmenting the entry snapshot with exit data."""
        snapshot = await RenderService._load_snapshot(trade_id)
        if not snapshot:
            return None

        drawing = snapshot.setdefault("drawing", {})
        drawing["exit_price"] = exit_price
        drawing["realized_pnl"] = realized_pnl
        drawing["realized_r"] = realized_r
        if mfe is not None:
            drawing["mfe_price"] = mfe
        if mae is not None:
            drawing["mae_price"] = mae
        if be_price is not None:
            drawing["be_price"] = be_price

        trade = snapshot.setdefault("trade", {})
        trade["exit_price"] = exit_price
        trade["realized_pnl"] = realized_pnl
        trade["realized_r"] = realized_r

        return RenderService._render(trade_id, snapshot)

    @staticmethod
    async def render_partial(trade_id: str, partial_price: float,
                             partial_pnl: float) -> Optional[str]:
        """Generate partial-close chart overlay."""
        snapshot = await RenderService._load_snapshot(trade_id)
        if not snapshot:
            return None
        drawing = snapshot.setdefault("drawing", {})
        drawing["partial_price"] = partial_price
        drawing["partial_pnl"] = partial_pnl
        return RenderService._render(trade_id, snapshot, suffix="partial")

    @staticmethod
    async def render_be(trade_id: str, be_price: float) -> Optional[str]:
        """Generate breakeven chart overlay."""
        snapshot = await RenderService._load_snapshot(trade_id)
        if not snapshot:
            return None
        drawing = snapshot.setdefault("drawing", {})
        drawing["be_price"] = be_price
        return RenderService._render(trade_id, snapshot, suffix="be")

    @staticmethod
    async def _load_snapshot(trade_id: str) -> Optional[Dict[str, Any]]:
        try:
            async with async_session_factory() as s:
                from sqlalchemy import select
                result = await s.execute(select(PaperTrade).where(PaperTrade.id == trade_id))
                trade = result.scalar_one_or_none()
                if trade and trade.snapshot:
                    return trade.snapshot
                logger.warning("No snapshot found for trade %s", trade_id)
                return None
        except Exception as e:
            logger.error("Failed to load snapshot for trade %s: %s", trade_id, e)
            return None

    @staticmethod
    def _render(trade_id: str, snapshot: Dict[str, Any],
                suffix: str = "entry") -> Optional[str]:
        """Delegate to tv_renderer. No calculations here."""
        try:
            from media.tv_renderer.renderer import tv_screenshot
            return tv_screenshot(trade_id, snapshot)
        except Exception as e:
            logger.error("Render failed for trade %s: %s", trade_id, e)
            return None


render_service = RenderService()
