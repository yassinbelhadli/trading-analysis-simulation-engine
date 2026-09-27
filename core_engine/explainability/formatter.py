"""Formatter — converts Explanation into text for Telegram, logs, etc.

This is the only place where human-readable text lives.
Display translations should delegate to translator.py for multi-language support.
"""

from __future__ import annotations
from typing import Dict, List, Optional

from .models import Explanation, Reason, Warning_, Invalidation
from .reason_codes import ReasonCode


# ── Reason code → human label (English defaults) ────────────────
_REASON_LABELS = {
    ReasonCode.BOS_BULLISH: "Bullish BOS",
    ReasonCode.BOS_BEARISH: "Bearish BOS",
    ReasonCode.CHOCH_BULLISH: "Bullish CHOCH",
    ReasonCode.CHOCH_BEARISH: "Bearish CHOCH",
    ReasonCode.MSS_BULLISH: "Bullish MSS",
    ReasonCode.MSS_BEARISH: "Bearish MSS",
    ReasonCode.SSL_SWEEP: "Sell-side Liquidity Swept",
    ReasonCode.BSL_SWEEP: "Buy-side Liquidity Swept",
    ReasonCode.PDH_BREAKOUT: "PDH Breakout",
    ReasonCode.PDL_BREAKOUT: "PDL Breakout",
    ReasonCode.FRESH_OB: "Fresh Order Block",
    ReasonCode.OB_MITIGATED: "OB Mitigation",
    ReasonCode.OB_RESPECTED: "OB Respected",
    ReasonCode.FVG_PRESENT: "FVG Present",
    ReasonCode.FVG_MITIGATED: "FVG Mitigated (filled)",
    ReasonCode.FVG_RESPECTED: "FVG Respected",
    ReasonCode.PRICE_AT_ZONE: "Price at Zone",
    ReasonCode.RETEST_CONFIRMED: "Retest Confirmed",
    ReasonCode.PROXIMITY_OK: "Price Proximity OK",
    ReasonCode.RR_FAVORABLE: "R:R Favorable",
    ReasonCode.STOP_TIGHT: "Stop Tight",
    ReasonCode.RISK_LIMIT_OK: "Risk Within Limits",
    ReasonCode.SCORE_HIGH: "Score: High",
    ReasonCode.SCORE_MEDIUM: "Score: Medium",
    ReasonCode.SCORE_LOW: "Score: Low",
    ReasonCode.NO_HIGH_IMPACT_NEWS: "No High-Impact News",
}


def reason_label(code: ReasonCode) -> str:
    return _REASON_LABELS.get(code, code.value)


# ── Main formatter ──────────────────────────────────────────────

def explain_to_text(exp: Explanation, detailed: bool = True) -> str:
    """Format an Explanation into human-readable text.

    Args:
        exp: Explanation from explainability engine
        detailed: if True, include warnings, invalidations, breakdown

    Returns:
        Formatted string (multi-line)
    """
    lines = []
    direction_icon = "BUY" if exp.verdict == "BUY" else "SELL" if exp.verdict == "SELL" else "WATCH"
    confidence_icon = {
        "VERY_HIGH": "HIGH", "HIGH": "HIGH",
        "MEDIUM": "MEDIUM", "LOW": "LOW", "VERY_LOW": "LOW",
    }.get(exp.confidence, exp.confidence)

    # ── Header ──
    symbol = exp.symbol or ""
    tf = exp.timeframe or ""
    header = f"{symbol} {tf}".strip()
    if header:
        lines.append(header)
    lines.append(f"Decision: {direction_icon}")
    lines.append(f"Score: {exp.score}/100")
    lines.append(f"Confidence: {confidence_icon}")
    lines.append("")

    # ── Confirmed reasons ──
    passed = exp.passed_reasons
    if passed:
        lines.append("Confirmed:")
        for r in passed:
            label = reason_label(r.code)
            detail = f" — {r.detail}" if r.detail and detailed else ""
            # Add evidence
            evidence_str = ""
            if r.evidence and detailed:
                ev_parts = []
                if r.evidence.price:
                    ev_parts.append(f"@{r.evidence.price}")
                if r.evidence.distance_pct is not None:
                    ev_parts.append(f"{r.evidence.distance_pct:.2f}%")
                if ev_parts:
                    evidence_str = f" ({', '.join(ev_parts)})"
            lines.append(f"  [+] {label}{detail}{evidence_str}")
        lines.append("")

    # ── Failed reasons ──
    failed = exp.failed_reasons
    if failed:
        lines.append("Failed Checks:")
        for r in failed:
            label = reason_label(r.code)
            detail = f" — {r.detail}" if r.detail and detailed else ""
            lines.append(f"  [-] {label}{detail}")
        lines.append("")

    # ── Warnings ──
    if detailed and exp.warnings:
        lines.append("Warnings:")
        for w in exp.warnings:
            icon = {"HIGH": "!", "MEDIUM": "-", "LOW": "."}.get(w.severity, "-")
            lines.append(f"  [{icon}] {w.message}")
        lines.append("")

    # ── Invalidations ──
    if detailed and exp.invalidations:
        lines.append("Invalidation Conditions:")
        for inv in exp.invalidations:
            price_str = f" @ {inv.trigger_price}" if inv.trigger_price else ""
            lines.append(f"  [!] {inv.description}{price_str}")
        lines.append("")

    # ── Breakdown (optional) ──
    if detailed and exp.breakdown:
        bd = exp.breakdown
        lines.append("Breakdown:")
        for key, val in [
            ("BOS", bd.bos), ("CHOCH", bd.choch), ("MSS", bd.mss),
            ("Sweep", bd.sweep), ("OB/FVG", bd.active_ob_fvg),
            ("PD Align", bd.pd_alignment),
        ]:
            if val:
                lines.append(f"  {key}: {val}")
        lines.append("")

    return "\n".join(lines)


def explain_to_dict(exp: Explanation) -> Dict:
    """Serialize Explanation to a plain dict for JSON/logging."""
    return {
        "verdict": exp.verdict,
        "score": exp.score,
        "confidence": exp.confidence,
        "symbol": exp.symbol,
        "timeframe": exp.timeframe,
        "timestamp": exp.timestamp,
        "reasons": [
            {
                "code": r.code.value,
                "label": reason_label(r.code),
                "passed": r.passed,
                "weight": r.weight,
                "detail": r.detail,
            }
            for r in exp.reasons
        ],
        "warnings": [
            {"code": w.code, "message": w.message, "severity": w.severity}
            for w in exp.warnings
        ],
        "invalidations": [
            {
                "condition": inv.condition,
                "description": inv.description,
                "trigger_price": inv.trigger_price,
                "direction": inv.direction,
            }
            for inv in exp.invalidations
        ],
    }
