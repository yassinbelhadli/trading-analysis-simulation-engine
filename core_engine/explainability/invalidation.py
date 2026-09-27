"""Invalidation builder — determines conditions that would break the trade."""

from __future__ import annotations
from typing import List, Dict, Any

from .models import Invalidation, Evidence
from .reason_codes import ReasonCode


def build_invalidations(snapshot: Dict[str, Any]) -> List[Invalidation]:
    """Build invalidation conditions from the snapshot.

    Each invalidation describes a price level / condition that,
    if triggered, means the original thesis is invalid.
    """
    result = []
    drawing = snapshot.get("drawing", {})
    trade = snapshot.get("trade", {})
    scoring = snapshot.get("scoring", {})
    structure = snapshot.get("structure", {})
    obs = snapshot.get("order_blocks", [])
    fvgs = snapshot.get("fvg", []) or snapshot.get("fvgs", [])

    direction = _detect_direction(drawing, trade, scoring)

    # ── OB breach invalidation ──
    for ob in obs:
        if ob.get("fresh") and not ob.get("mitigated"):
            bottom = float(ob.get("bottom", 0))
            top = float(ob.get("top", 0))
            if bottom > top:
                bottom, top = top, bottom
            ob_type = (ob.get("type") or "").upper()
            # For bullish OB: invalidation = close below bottom
            # For bearish OB: invalidation = close above top
            if direction == "BUY" and "BULLISH" in ob_type:
                result.append(Invalidation(
                    condition="CLOSE_BELOW_OB",
                    description="Close below Order Block",
                    trigger_price=bottom,
                    direction="BELOW",
                    evidence=Evidence(price=bottom, zone_id=ob.get("anchor_candle") and str(ob["anchor_candle"])),
                ))
            elif direction == "SELL" and "BEARISH" in ob_type:
                result.append(Invalidation(
                    condition="CLOSE_ABOVE_OB",
                    description="Close above Order Block",
                    trigger_price=top,
                    direction="ABOVE",
                    evidence=Evidence(price=top),
                ))

    # ── New MSS invalidation ──
    mss = structure.get("mss") or structure.get("MSS")
    if mss:
        mss_price = mss.get("price", 0)
        mss_dir = (mss.get("direction") or "").upper()
        if direction == "BUY" and mss_dir == "BEARISH":
            result.append(Invalidation(
                condition="NEW_BEARISH_MSS",
                description="New bearish Market Structure Shift",
                trigger_price=mss_price,
                direction="BELOW",
            ))
        elif direction == "SELL" and mss_dir == "BULLISH":
            result.append(Invalidation(
                condition="NEW_BULLISH_MSS",
                description="New bullish Market Structure Shift",
                trigger_price=mss_price,
                direction="ABOVE",
            ))

    # ── FVG fill invalidation ──
    for fvg in fvgs:
        if not fvg.get("mitigated"):
            top = float(fvg.get("top", 0))
            bottom = float(fvg.get("bottom", 0))
            if bottom > top:
                top, bottom = bottom, top
            fvg_type = (fvg.get("type") or "").upper()
            if direction == "BUY" and "BULLISH" in fvg_type:
                result.append(Invalidation(
                    condition="FVG_FILLED",
                    description="FVG fully filled (gap closed)",
                    trigger_price=bottom,
                    direction="BELOW",
                ))
            elif direction == "SELL" and "BEARISH" in fvg_type:
                result.append(Invalidation(
                    condition="FVG_FILLED",
                    description="FVG fully filled (gap closed)",
                    trigger_price=top,
                    direction="ABOVE",
                ))

    # ── SL hit — always an invalidation ──
    sl = drawing.get("sl_price") or trade.get("sl_price")
    if sl:
        sl_dir = "BELOW" if direction == "BUY" else "ABOVE"
        result.append(Invalidation(
            condition="STOP_LOSS_HIT",
            description="Stop Loss triggered",
            trigger_price=float(sl),
            direction=sl_dir,
        ))

    return result


def _detect_direction(drawing: dict, trade: dict, scoring: dict) -> str:
    raw = (drawing.get("buy_sell") or trade.get("direction")
           or scoring.get("direction") or "").upper()
    if raw in ("BUY", "BULLISH"):
        return "BUY"
    if raw in ("SELL", "BEARISH"):
        return "SELL"
    return "NEUTRAL"
