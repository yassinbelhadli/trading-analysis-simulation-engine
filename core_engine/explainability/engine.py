"""Explainability Engine — builds a structured Explanation (Decision Graph) from a Snapshot.

This is the single source of truth for WHY a trade decision was made.
All downstream consumers read from Explanation — they never re-analyse the snapshot.

Flow:
    Snapshot → [Structure Analyzer, Liquidity Analyzer, OBAnalyzer,
                FVGAnalyzer, RiskAnalyzer, ScoringAnalyzer] → Explanation
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
from datetime import datetime

from .models import (
    Explanation, Reason, Evidence, Warning_, Invalidation,
    Breakdown, ConfidenceLevel,
)
from .reason_codes import ReasonCode
from .confidence import compute_confidence
from .invalidation import build_invalidations


def build_explanation(snapshot: Dict[str, Any]) -> Explanation:
    """Build a complete Explanation from a detection snapshot.

    Args:
        snapshot: dict from detection engine (setup_detector.to_snapshot()
                  or ict_analysis.build_snapshot())

    Returns:
        Explanation — immutable Decision Graph
    """
    meta = snapshot.get("metadata", {}) or {}
    drawing = snapshot.get("drawing", {}) or {}
    trade = snapshot.get("trade", {}) or {}
    structure = snapshot.get("structure", {})
    scoring = snapshot.get("scoring", {}) or {}
    obs = snapshot.get("order_blocks", [])
    fvgs = snapshot.get("fvg", []) or snapshot.get("fvgs", [])
    liquid = snapshot.get("liquidity", {}) or {}
    session = snapshot.get("session", {}) or {}
    candles = snapshot.get("chart", {}).get("ohlc", [])

    direction = _detect_direction(drawing, trade, scoring)
    reasons: List[Reason] = []
    warnings: List[Warning_] = []

    # ── Structure reasons ──
    reasons.extend(_analyze_structure(structure, direction))

    # ── Liquidity reasons ──
    reasons.extend(_analyze_liquidity(liquid, session, structure, direction))

    # ── Order Block reasons ──
    reasons.extend(_analyze_obs(obs, direction))

    # ── FVG reasons ──
    reasons.extend(_analyze_fvgs(fvgs, direction))

    # ── Risk reasons ──
    reasons.extend(_analyze_risk(drawing, trade, direction, candles))

    # ── Scoring / confidence ──
    score = scoring.get("score", _compute_score(reasons))
    breakdown = _extract_breakdown(scoring, reasons)
    confidence = compute_confidence(score, reasons, breakdown)

    # ── Warnings ──
    warnings.extend(_build_warnings(snapshot, direction))

    # ── Invalidations ──
    invalidations = build_invalidations(snapshot)

    # ── Verdict ──
    verdict = _determine_verdict(direction, score, reasons)

    return Explanation(
        verdict=verdict,
        score=score,
        confidence=confidence,
        reasons=reasons,
        breakdown=breakdown,
        warnings=warnings,
        invalidations=invalidations,
        timestamp=datetime.utcnow().isoformat(),
        setup_id=meta.get("setup_id", ""),
        symbol=meta.get("symbol", ""),
        timeframe=meta.get("timeframe", ""),
    )


# ── Analyzers ────────────────────────────────────────────────────

def _analyze_structure(structure: Dict, direction: str) -> List[Reason]:
    reasons = []

    bos = structure.get("bos") or structure.get("BOS")
    if bos:
        bos_dir = (bos.get("direction") or "").upper()
        price = bos.get("price")
        passed = (direction == "BUY" and "BULLISH" in bos_dir) or \
                 (direction == "SELL" and "BEARISH" in bos_dir)
        reasons.append(Reason(
            code=ReasonCode.BOS_BULLISH if "BULLISH" in bos_dir else ReasonCode.BOS_BEARISH,
            passed=passed,
            weight=20,
            evidence=Evidence(price=price),
            detail=f"BOS at {price}" if price else "BOS detected",
        ))

    choch = structure.get("choch") or structure.get("CHOCH")
    if choch:
        ch_dir = (choch.get("direction") or "").upper()
        price = choch.get("price")
        passed = (direction == "BUY" and "BULLISH" in ch_dir) or \
                 (direction == "SELL" and "BEARISH" in ch_dir)
        reasons.append(Reason(
            code=ReasonCode.CHOCH_BULLISH if "BULLISH" in ch_dir else ReasonCode.CHOCH_BEARISH,
            passed=passed,
            weight=15,
            evidence=Evidence(price=price),
        ))

    mss_ = structure.get("mss") or structure.get("MSS")
    if mss_:
        m_dir = (mss_.get("direction") or "").upper()
        price = mss_.get("price")
        passed = (direction == "BUY" and "BULLISH" in m_dir) or \
                 (direction == "SELL" and "BEARISH" in m_dir)
        reasons.append(Reason(
            code=ReasonCode.MSS_BULLISH if "BULLISH" in m_dir else ReasonCode.MSS_BEARISH,
            passed=passed,
            weight=20,
            evidence=Evidence(price=price),
        ))

    return reasons


def _analyze_liquidity(liquid: Dict, session: Dict,
                       structure: Dict, direction: str) -> List[Reason]:
    reasons = []

    sweep = liquid.get("sweep_price") or liquid.get("sweep") or structure.get("sweep_price")
    if sweep is not None:
        sweep_type = (liquid.get("sweep_type") or "").upper()
        passed = (direction == "BUY" and "SELL" in sweep_type) or \
                 (direction == "SELL" and "BUY" in sweep_type)
        code = ReasonCode.SSL_SWEEP if "SELL" in sweep_type else ReasonCode.BSL_SWEEP
        reasons.append(Reason(
            code=code,
            passed=passed,
            weight=15,
            evidence=Evidence(price=float(sweep)),
        ))

    # PDH / PDL break
    pdh = session.get("pdh") or liquid.get("pdh") or structure.get("pdh")
    pdl = session.get("pdl") or liquid.get("pdl") or structure.get("pdl")
    if pdh and direction == "BUY":
        reasons.append(Reason(
            code=ReasonCode.PDH_BREAKOUT,
            passed=True,
            weight=5,
            evidence=Evidence(price=float(pdh)),
        ))
    if pdl and direction == "SELL":
        reasons.append(Reason(
            code=ReasonCode.PDL_BREAKOUT,
            passed=True,
            weight=5,
            evidence=Evidence(price=float(pdl)),
        ))

    return reasons


def _analyze_obs(obs: List[Dict], direction: str) -> List[Reason]:
    reasons = []
    has_fresh = False
    has_mitigated = False

    for ob in obs:
        ob_dir = (ob.get("type") or "").upper()
        ob_aligned = (direction == "BUY" and "BULLISH" in ob_dir) or \
                     (direction == "SELL" and "BEARISH" in ob_dir)
        if not ob_aligned:
            continue

        if ob.get("fresh"):
            has_fresh = True
            reasons.append(Reason(
                code=ReasonCode.FRESH_OB,
                passed=True,
                weight=20,
                evidence=Evidence(
                    price=ob.get("bottom") or ob.get("top"),
                    zone_id=str(ob.get("anchor_candle", "")),
                ),
            ))
        elif ob.get("mitigated"):
            has_mitigated = True
        else:
            # Present but not fresh — still counts but less
            has_fresh = True
            reasons.append(Reason(
                code=ReasonCode.OB_RESPECTED,
                passed=True,
                weight=10,
                evidence=Evidence(zone_id=str(ob.get("anchor_candle", ""))),
            ))

    if not has_fresh and not has_mitigated:
        reasons.append(Reason(
            code=ReasonCode.FRESH_OB,
            passed=False,
            weight=10,
            detail="No aligned Order Block found",
        ))

    return reasons


def _analyze_fvgs(fvgs: List[Dict], direction: str) -> List[Reason]:
    reasons = []
    has_active = False

    for fvg in fvgs:
        f_dir = (fvg.get("type") or "").upper()
        f_aligned = (direction == "BUY" and "BULLISH" in f_dir) or \
                    (direction == "SELL" and "BEARISH" in f_dir)
        if not f_aligned:
            continue

        if not fvg.get("mitigated"):
            has_active = True
            reasons.append(Reason(
                code=ReasonCode.FVG_PRESENT,
                passed=True,
                weight=10,
                evidence=Evidence(
                    price=fvg.get("top"),
                    zone_id=str(fvg.get("candle", "")),
                ),
            ))
        else:
            reasons.append(Reason(
                code=ReasonCode.FVG_RESPECTED,
                passed=True,
                weight=5,
                evidence=Evidence(price=fvg.get("top")),
            ))

    if not has_active:
        for fvg in fvgs:
            f_dir = (fvg.get("type") or "").upper()
            f_aligned = (direction == "BUY" and "BULLISH" in f_dir) or \
                        (direction == "SELL" and "BEARISH" in f_dir)
            if f_aligned and fvg.get("mitigated"):
                reasons.append(Reason(
                    code=ReasonCode.FVG_MITIGATED,
                    passed=False,
                    weight=5,
                    detail="FVG already filled",
                ))
                break

    return reasons


def _analyze_risk(drawing: Dict, trade: Dict, direction: str,
                  candles: List) -> List[Reason]:
    reasons = []

    entry = drawing.get("entry_price") or trade.get("entry_price")
    sl = drawing.get("sl_price") or trade.get("sl_price")
    tp = drawing.get("tp", []) or trade.get("tp_prices", [])

    if entry and sl:
        entry = float(entry)
        sl = float(sl)
        risk_dist = abs(entry - sl)
        if risk_dist > 0:
            avg_price = (max(c["high"] for c in candles[-20:]) +
                         min(c["low"] for c in candles[-20:])) / 2 if candles else entry
            risk_pct = risk_dist / avg_price * 100 if avg_price else 0
            if risk_pct < 1.0:
                reasons.append(Reason(
                    code=ReasonCode.STOP_TIGHT,
                    passed=True,
                    weight=5,
                    evidence=Evidence(distance_pct=round(risk_pct, 2)),
                    detail=f"SL {risk_pct:.2f}% from entry",
                ))
            else:
                reasons.append(Reason(
                    code=ReasonCode.STOP_TIGHT,
                    passed=False,
                    weight=5,
                    evidence=Evidence(distance_pct=round(risk_pct, 2)),
                    detail=f"Wide SL ({risk_pct:.2f}%)",
                ))

            if tp:
                tp_prices = [float(t) for t in (tp if isinstance(tp, list) else [tp])]
                best_tp = max(tp_prices) if direction == "BUY" else min(tp_prices)
                rr = abs(best_tp - entry) / risk_dist
                if rr >= 2.0:
                    reasons.append(Reason(
                        code=ReasonCode.RR_FAVORABLE,
                        passed=True,
                        weight=10,
                        evidence=Evidence(extra={"rr": round(rr, 2)}),
                        detail=f"R:R = 1:{rr:.1f}",
                    ))
                else:
                    reasons.append(Reason(
                        code=ReasonCode.RR_FAVORABLE,
                        passed=False,
                        weight=10,
                        evidence=Evidence(extra={"rr": round(rr, 2)}),
                        detail=f"Low R:R = 1:{rr:.1f}",
                    ))

    return reasons


# ── Warnings ─────────────────────────────────────────────────────

def _build_warnings(snapshot: Dict, direction: str) -> List[Warning_]:
    warnings = []
    drawing = snapshot.get("drawing", {})
    trade = snapshot.get("trade", {})

    entry = drawing.get("entry_price") or trade.get("entry_price")
    sl = drawing.get("sl_price") or trade.get("sl_price")

    if entry and sl:
        entry, sl = float(entry), float(sl)
        risk_dist = abs(entry - sl)
        avg_price = entry
        risk_pct = risk_dist / avg_price * 100 if avg_price else 0
        if risk_pct > 2.0:
            warnings.append(Warning_(
                code="WIDE_STOP",
                message="Stop loss is wider than 2% — consider position sizing",
                severity="MEDIUM",
                evidence=Evidence(distance_pct=round(risk_pct, 2)),
            ))

    return warnings


# ── Helpers ──────────────────────────────────────────────────────

def _detect_direction(drawing: dict, trade: dict, scoring: dict) -> str:
    raw = (drawing.get("buy_sell") or trade.get("direction")
           or scoring.get("direction") or "").upper()
    if raw in ("BUY", "BULLISH"):
        return "BUY"
    if raw in ("SELL", "BEARISH"):
        return "SELL"
    return "NEUTRAL"


def _compute_score(reasons: List[Reason]) -> int:
    return min(100, sum(r.weight for r in reasons if r.passed))


def _extract_breakdown(scoring: Dict, reasons: List[Reason]) -> Breakdown:
    # Prefer breakdown from scoring engine if present
    bd = scoring.get("breakdown", {}) if isinstance(scoring, dict) else {}
    if bd:
        return Breakdown(
            bos=bd.get("bos", 0),
            hidden_bos=bd.get("hidden_bos", 0),
            choch=bd.get("choch", 0),
            mss=bd.get("mss", 0),
            sweep=bd.get("sweep", 0),
            active_ob_fvg=bd.get("active_ob_fvg", 0),
            pd_alignment=bd.get("pd_alignment", 0),
        )

    # Fallback: derive from reasons
    from .reason_codes import ReasonCode
    by_code = {}
    for r in reasons:
        if r.passed:
            by_code[r.code.value] = r.weight

    return Breakdown(
        bos=by_code.get("BOS_BULLISH", 0) or by_code.get("BOS_BEARISH", 0),
        choch=by_code.get("CHOCH_BULLISH", 0) or by_code.get("CHOCH_BEARISH", 0),
        mss=by_code.get("MSS_BULLISH", 0) or by_code.get("MSS_BEARISH", 0),
        sweep=by_code.get("SSL_SWEEP", 0) or by_code.get("BSL_SWEEP", 0),
        active_ob_fvg=by_code.get("FRESH_OB", 0) or by_code.get("FVG_PRESENT", 0),
        pd_alignment=by_code.get("PDH_BREAKOUT", 0) or by_code.get("PDL_BREAKOUT", 0),
    )


def _determine_verdict(direction: str, score: int, reasons: List[Reason]) -> str:
    if direction in ("BUY", "SELL") and score >= 60:
        return direction
    if score >= 40:
        return "WATCH"
    return "SKIP"
