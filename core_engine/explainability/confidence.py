"""Confidence calculator — maps score + reason profile → confidence level."""

from __future__ import annotations
from typing import List

from .models import Reason, ConfidenceLevel, Breakdown


def compute_confidence(score: int, reasons: List[Reason],
                       breakdown: Breakdown = None) -> str:
    """Determine confidence level from score, reasons, and breakdown.

    Rules:
        VERY_HIGH:  score >= 85 AND all structural reasons passed
        HIGH:       score >= 70
        MEDIUM:     score >= 50
        LOW:        score >= 30
        VERY_LOW:   otherwise
    """
    if score >= 85 and _all_structure_passed(reasons):
        return ConfidenceLevel.VERY_HIGH
    if score >= 70:
        return ConfidenceLevel.HIGH
    if score >= 50:
        return ConfidenceLevel.MEDIUM
    if score >= 30:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.VERY_LOW


def _all_structure_passed(reasons: List[Reason]) -> bool:
    """Check if all structural checks (BOS, CHOCH, MSS) passed."""
    from .reason_codes import ReasonCode
    struct_codes = {
        ReasonCode.BOS_BULLISH, ReasonCode.BOS_BEARISH,
        ReasonCode.CHOCH_BULLISH, ReasonCode.CHOCH_BEARISH,
        ReasonCode.MSS_BULLISH, ReasonCode.MSS_BEARISH,
    }
    struct_reasons = [r for r in reasons if r.code in struct_codes]
    return all(r.passed for r in struct_reasons)
