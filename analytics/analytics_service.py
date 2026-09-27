from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select

from database.db import async_session_factory
from database.models import PaperTrade
from analytics.metrics_calculator import (
    TradeMetrics,
    close_category,
    is_strategic,
    compute_metrics,
    compute_strategic_metrics,
    compute_by_category,
    compute_by_symbol,
    compute_by_session,
    compute_by_regime,
    compute_by_direction,
    compute_by_score_bucket,
    compute_distributions,
    compute_timeline,
    metrics_to_dict,
)

ROOT = Path(__file__).resolve().parents[1]
ENGINE_LOG = ROOT / "logs" / "engine.log"

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self) -> None:
        self._cached: Optional[dict] = None
        self._cached_at: Optional[datetime] = None

    async def fetch_all_trades(self) -> List[PaperTrade]:
        async with async_session_factory() as s:
            result = await s.execute(select(PaperTrade))
            return list(result.scalars().all())

    async def fetch_strategic_trades(self) -> List[PaperTrade]:
        all_trades = await self.fetch_all_trades()
        return [t for t in all_trades if is_strategic(t)]

    async def compute_full_report(self, force: bool = False) -> dict:
        if self._cached is not None and not force:
            return self._cached

        all_trades = await self.fetch_all_trades()
        closed = [t for t in all_trades if t.status == "CLOSED"]
        strategic = [t for t in all_trades if is_strategic(t)]
        active = [t for t in all_trades if t.status in ("PLANNED", "FILLED")]

        report: dict = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_range": self._data_range(all_trades),
            "overview": {
                "all_trades_count": len(all_trades),
                "closed_count": len(closed),
                "strategic_count": len(strategic),
                "stale_cleanup_count": len(closed) - len(strategic),
                "active_count": len(active),
                "planned_count": sum(1 for t in all_trades if t.status == "PLANNED"),
                "filled_count": sum(1 for t in all_trades if t.status == "FILLED"),
                "batch1_count": sum(1 for t in strategic if getattr(t, "validation_batch", 1) == 1),
                "batch2_count": sum(1 for t in strategic if getattr(t, "validation_batch", 1) == 2),
            },
            "total": metrics_to_dict(compute_metrics(closed)),
            "strategic": metrics_to_dict(compute_strategic_metrics(all_trades)),
            "active_lock": self._compute_active_lock(active),
            "by_category": {
                k: metrics_to_dict(v) for k, v in compute_by_category(closed).items()
            },
            "by_symbol": {
                k: metrics_to_dict(v) for k, v in compute_by_symbol(closed).items()
            },
            "by_session": {
                k: metrics_to_dict(v) for k, v in compute_by_session(closed).items()
            },
            "by_market_regime": {
                k: metrics_to_dict(v) for k, v in compute_by_regime(closed).items()
            },
            "by_direction": {
                k: metrics_to_dict(v) for k, v in compute_by_direction(closed).items()
            },
            "by_score_bucket": {
                k: metrics_to_dict(v) for k, v in compute_by_score_bucket(closed).items()
            },
            "distributions": compute_distributions(closed),
            "timeline": compute_timeline(closed),
        }

        self._cached = report
        self._cached_at = datetime.now(timezone.utc)
        return report

    @staticmethod
    def _data_range(trades: List[PaperTrade]) -> dict:
        created = [t.created_at for t in trades if t.created_at]
        closed_dt = [t.closed_at for t in trades if t.closed_at and t.status == "CLOSED"]
        return {
            "first_trade": min(created).isoformat() if created else None,
            "last_trade": max(created).isoformat() if created else None,
            "first_close": min(closed_dt).isoformat() if closed_dt else None,
            "last_close": max(closed_dt).isoformat() if closed_dt else None,
        }

    def invalidate_cache(self) -> None:
        self._cached = None
        self._cached_at = None

    # ── Active Lock Analytics ──────────────────────────────────────────

    @staticmethod
    def _parse_log_skipped_setups() -> dict:
        """Parse engine.log for skipped-setup counters (total + per symbol)."""
        log_path = ENGINE_LOG
        if not log_path.exists():
            return {"skipped_setups": 0, "by_symbol": {}}

        total = 0
        by_symbol: dict[str, int] = {}
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
            # Total from latest counters line (format: 'setups_skipped_active': 599)
            for m in re.finditer(r"'setups_skipped_active':\s*(\d+)", text):
                total = int(m.group(1))
            # Per-symbol breakdown
            for m in re.finditer(r"Setup skipped \(active trade\) \| symbol=(\S+)", text):
                sym = m.group(1)
                by_symbol[sym] = by_symbol.get(sym, 0) + 1
        except Exception:
            logger.warning("Failed to parse engine.log for active lock analytics", exc_info=True)

        return {"skipped_setups": total, "by_symbol": by_symbol}

    @staticmethod
    def _compute_active_lock(active_trades: list) -> dict:
        now = datetime.now(timezone.utc)
        unique_symbols = len(set(t.symbol for t in active_trades))
        lock = {
            "active_count": len(active_trades),
            "unique_symbols": unique_symbols,
            "slots_total": 3,
            "slots_free": 3 - unique_symbols,
            "by_symbol": {},
            "lock_reason": {"ACTIVE": 0, "BREAK_EVEN": 0},
        }

        for t in active_trades:
            age_min = round((now - t.created_at).total_seconds() / 60, 1)
            is_be = bool(t.breakeven_activated)
            reason = "BREAK_EVEN" if is_be else "ACTIVE"
            lock["lock_reason"][reason] = lock["lock_reason"].get(reason, 0) + 1
            lock["by_symbol"][t.symbol] = {
                "direction": t.direction,
                "status": t.status,
                "breakeven_activated": is_be,
                "lock_duration_minutes": age_min,
                "entry_price": t.entry_price,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
            }

        # Merge log-based skipped counts
        log_stats = AnalyticsService._parse_log_skipped_setups()
        lock["skipped_setups"] = log_stats["skipped_setups"]
        # Enrich per-symbol with log counts where available
        for sym, info in lock["by_symbol"].items():
            info["skipped_setups_log"] = log_stats["by_symbol"].get(sym, 0)

        return lock


analytics_service = AnalyticsService()
