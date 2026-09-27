from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def explain_snapshot(snapshot: Dict) -> str:
    """Generate natural-language explanations from a canonical snapshot dict
    (as produced by setup_mapper.setup_to_snapshot or candidate.to_snapshot)."""
    parts: List[str] = []

    structure = snapshot.get("structure", {}) or {}
    liquidity = snapshot.get("liquidity", {}) or {}
    obs = snapshot.get("order_blocks", []) or []
    fvgs = snapshot.get("fvg", []) or []
    pd = snapshot.get("premium_discount", {}) or {}
    session = snapshot.get("session", {}) or {}
    scoring = snapshot.get("scoring", {}) or {}
    drawing = snapshot.get("drawing", {}) or {}
    reasons = scoring.get("reasons", []) or []
    direction = drawing.get("buy_sell", scoring.get("direction", ""))

    # ── Try setup_to_snapshot format (nested structure entries) ──
    bos = structure.get("bos")
    choch = structure.get("choch")
    mss = structure.get("mss")
    swings = structure.get("swings", [])

    has_bos = bool(bos) or structure.get("bos_detected", False)
    has_choch = bool(choch) or structure.get("choch_detected", False)
    has_mss = bool(mss) or structure.get("mss_detected", False)

    # Read sweep info from both formats
    sweep_price = _get_first(liquidity, "sweep_price")
    sweep_type = _get_first(liquidity, "sweep_type")
    sweep_detected = sweep_price is not None or liquidity.get("sweep_detected", False)

    # PDH/PDL from either format
    pdh = _get_first(liquidity, "pdh") or _get_first(session, "pdh")
    pdl = _get_first(liquidity, "pdl") or _get_first(session, "pdl")

    # Scoring
    score = scoring.get("score", 0) or 0
    confidence = scoring.get("confidence_score", 0) or 0

    # ── Build narrative ──

    # Direction summary
    if direction:
        dir_label = "bearish" if direction == "SELL" else "bullish"
        parts.append(f"Overall bias is <b>{dir_label}</b> with score {score:.0f}/100 and confidence {confidence:.0f}%.")

    # Trend context — try both formats
    trend = structure.get("trend", "")
    if trend:
        trend_map = {
            "STRONG_BULLISH": "Strong bullish momentum across higher timeframe.",
            "BULLISH": "Bullish bias on higher timeframe.",
            "NEUTRAL": "Market consolidating with no clear directional bias.",
            "BEARISH": "Bearish bias on higher timeframe.",
            "STRONG_BEARISH": "Strong bearish momentum across higher timeframe.",
        }
        parts.append(trend_map.get(trend, f"HTF trend: {trend}."))

    # Session / kill zone
    session_label = session.get("label", "")
    if session_label:
        parts.append(f"Price trading in the <b>{session_label}</b> session.")
    if session.get("is_kill_zone"):
        zones = session.get("kill_zones_active", [])
        if zones:
            parts.append(f"Active kill-zone: {', '.join(zones)}.")

    # BOS
    if has_bos:
        if isinstance(bos, dict):
            bos_dir = bos.get("direction", "")
            parts.append("Market structure broke "
                         f"{'up' if bos_dir == 'BULLISH' else 'down'} (BOS).")
        else:
            parts.append("Market structure break confirmed (BOS).")

    # CHoCH
    if has_choch:
        if isinstance(choch, dict):
            choch_dir = choch.get("direction", "")
            parts.append("Character change of market structure (CHoCH).")
        else:
            parts.append("Character change confirmed (CHoCH).")

    # MSS
    if has_mss:
        if isinstance(mss, dict):
            mss_dir = mss.get("direction", "")
            parts.append("Market structure shift "
                         f"{'bullish' if mss_dir == 'BULLISH' else 'bearish'} (MSS).")
        else:
            parts.append("Market structure shift confirmed (MSS).")

    # Liquidity sweep
    if sweep_detected:
        readable = _readable_sweep(sweep_type or "")
        parts.append(f"{readable} liquidity swept.")

    # PDH / PDL
    if pdh and direction == "SELL":
        parts.append("Price rejected at previous day high (PDH).")
    if pdl and direction == "BUY":
        parts.append("Price respected previous day low (PDL).")

    # Order Blocks
    for ob in obs:
        ob_type = ob.get("type", "")
        if ob.get("fresh", False) and ob_type:
            label = ob_type.replace("_", " ").title()
            parts.append(f"Fresh order block providing {'support' if 'BULLISH' in ob_type else 'resistance'}.")

    # FVG
    for f in fvgs:
        fvg_type = f.get("type", "")
        size = f.get("size", 0)
        if fvg_type:
            fvg_dir = "bullish" if "BULLISH" in fvg_type else "bearish"
            size_str = f" ({size:.1f} pts)" if size else ""
            parts.append(f"Unfilled {fvg_dir} FVG{size_str} — price expected to react.")

    # Premium / Discount
    zone = pd.get("zone", "")
    if zone:
        if "PREMIUM" in zone:
            parts.append("Price reached premium zone — selling pressure expected.")
        elif "DISCOUNT" in zone:
            parts.append("Price reached discount zone — buying pressure expected.")

    # Fallback: reasons list
    if not parts and reasons:
        for r in reasons[:5]:
            parts.append(f"{_readable_reason(r, direction)}")

    return "\n".join(parts)


def explain_trade_reasons(reasons: List[str], direction: str) -> str:
    if not reasons:
        return ""
    lines: List[str] = []
    for r in reasons:
        lines.append(f"{_readable_reason(r, direction)}")
    return "\n".join(lines)


def explain_snapshot_bullets(snapshot: Dict) -> List[str]:
    """Compact checklist of confirmed ICT reasons for the signal caption.

    Returns short labels like ['BOS', 'MSS', 'Liquidity Sweep',
    'Fresh Order Block', 'FVG Confluence'] so the caption stays clean and
    the full structure chart is reserved for the "View Analysis" button.
    """
    bullets: List[str] = []
    structure = snapshot.get("structure", {}) or {}
    liquidity = snapshot.get("liquidity", {}) or {}
    obs = snapshot.get("order_blocks", []) or []
    fvgs = snapshot.get("fvg", []) or snapshot.get("fvgs", []) or []
    scoring = snapshot.get("scoring", {}) or {}
    reasons = scoring.get("reasons", []) or []

    if structure.get("bos") or structure.get("bos_detected"):
        bullets.append("BOS")
    if structure.get("choch") or structure.get("choch_detected"):
        bullets.append("CHoCH")
    if structure.get("mss") or structure.get("mss_detected"):
        bullets.append("MSS")
    if (liquidity.get("sweep_price") is not None) or liquidity.get("sweep_detected"):
        bullets.append("Liquidity Sweep")
    for ob in obs:
        if ob.get("fresh") and ob.get("type"):
            bullets.append("Fresh Order Block")
            break
    if fvgs:
        bullets.append("FVG Confluence")

    if not bullets and reasons:
        for r in reasons[:6]:
            base = _readable_reason(r, scoring.get("direction", ""))
            bullets.append(base)

    return bullets


def _readable_sweep(sweep_type: str) -> str:
    mapping = {
        "EQH": "Equal highs",
        "EQL": "Equal lows",
        "PDH_SWEEP": "Previous day high",
        "PDL_SWEEP": "Previous day low",
        "ASIAN_HIGH": "Asian session high",
        "ASIAN_LOW": "Asian session low",
        "BUY_SWEEP": "Buy-side liquidity",
        "SELL_SWEEP": "Sell-side liquidity",
    }
    return mapping.get(sweep_type, sweep_type.replace("_", " ").title())


def _readable_reason(reason: str, direction: str) -> str:
    reason_map = {
        "MSS": "Market structure shift confirms directional bias",
        "CHoCH": "Character change confirms trend shift",
        "BOS": "Break of structure confirms momentum",
        "Sweep_EQH": "Equal highs swept — liquidity grab confirmed",
        "Sweep_EQL": "Equal lows swept — liquidity grab confirmed",
        "Sweep_PDH": "Previous day high swept — liquidity taken",
        "Sweep_PDL": "Previous day low swept — liquidity taken",
        "FVG": "Fair value gap left unfilled — price expected to return",
        "OB": "Order block providing support/resistance",
        "Fresh_OB": "Fresh order block providing reactive entry",
        "Bearish_FVG": "Bearish fair value gap — selling pressure expected",
        "Bullish_FVG": "Bullish fair value gap — buying pressure expected",
        "PD_Rejection": "Premium/discount zone rejection",
    }
    base = reason_map.get(reason, reason)
    return base


def _get_first(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None
