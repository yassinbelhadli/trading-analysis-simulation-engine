"""Immutable data models for the Explainability Engine — Decision Graph nodes."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .reason_codes import ReasonCode


# ── Evidence ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class Evidence:
    """Supporting data for a reason/warning/invalidation."""
    price: Optional[float] = None
    time: Optional[str] = None
    candle_index: Optional[int] = None
    zone_id: Optional[str] = None
    distance_pct: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)


# ── Reason ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class Reason:
    """A single reason contributing to the decision.

    code:      machine-readable, language-independent
    passed:    True = contributes positively, False = failed check
    weight:    contribution to total score (0-100)
    evidence:  supporting data (prices, times, IDs)
    detail:    optional human-readable note (for debugging)
    """
    code: ReasonCode
    passed: bool
    weight: int = 0
    evidence: Optional[Evidence] = None
    detail: str = ""


# ── Warning ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class Warning_:
    """A condition to monitor, not a reason to reject.

    code:      machine-readable (e.g. 'LONDON_CLOSE', 'LOW_ATR')
    message:   short description
    severity:  LOW | MEDIUM | HIGH
    evidence:  supporting data
    """
    code: str
    message: str
    severity: str = "LOW"
    evidence: Optional[Evidence] = None


# ── Invalidation ─────────────────────────────────────────────────
@dataclass(frozen=True)
class Invalidation:
    """A condition that, if triggered, invalidates the trade.

    condition:   machine-readable (e.g. 'CLOSE_BELOW_OB')
    description: human-readable description
    trigger_price: the price level to watch
    direction:   ABOVE | BELOW
    """
    condition: str
    description: str
    trigger_price: Optional[float] = None
    direction: str = "BELOW"
    evidence: Optional[Evidence] = None


# ── Breakdown ────────────────────────────────────────────────────
@dataclass(frozen=True)
class Breakdown:
    """Component scores broken down by category."""
    bos: int = 0
    hidden_bos: int = 0
    choch: int = 0
    mss: int = 0
    sweep: int = 0
    active_ob_fvg: int = 0
    pd_alignment: int = 0


# ── Confidence ───────────────────────────────────────────────────
class ConfidenceLevel:
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


# ── Explanation ──────────────────────────────────────────────────
@dataclass(frozen=True)
class Explanation:
    """Complete decision graph — the single source of truth for WHY.

    All downstream consumers (Renderer, Telegram, Dashboard, Logs)
    read this object. They never re-analyse the snapshot.
    """
    verdict: str              # BUY | SELL | NEUTRAL | SKIP
    score: int                # 0-100
    confidence: str           # ConfidenceLevel
    reasons: List[Reason]
    breakdown: Optional[Breakdown] = None
    warnings: List[Warning_] = field(default_factory=list)
    invalidations: List[Invalidation] = field(default_factory=list)
    timestamp: str = ""
    setup_id: str = ""
    symbol: str = ""
    timeframe: str = ""

    @property
    def passed_reasons(self) -> List[Reason]:
        return [r for r in self.reasons if r.passed]

    @property
    def failed_reasons(self) -> List[Reason]:
        return [r for r in self.reasons if not r.passed]

    @property
    def total_weight(self) -> int:
        return sum(r.weight for r in self.reasons if r.passed)

    @property
    def is_tradeable(self) -> bool:
        return self.verdict in ("BUY", "SELL") and self.score >= 60
