"""SetupMapper — converts SetupCandidate to the canonical snapshot format.

The builders in renderer_v2 expect a specific snapshot structure.
This mapper transforms a SetupCandidate (or raw detection dict) into
that canonical format, then runs the builder pipeline.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from core_engine.detection.setup_detector import SetupCandidate

from renderer_v2.scene import Scene
from renderer_v2.builder import build_scene


def setup_to_snapshot(candidate: SetupCandidate) -> Dict[str, Any]:
    """Convert a SetupCandidate into the canonical snapshot format
    that the builder pipeline expects.

    Args:
        candidate: detected setup with structure, OB, FVG, etc.

    Returns:
        Canonical snapshot dict consumable by build_scene().
    """
    struct = candidate.structure
    liq = candidate.liquidity
    ob = candidate.ob
    fvg = candidate.fvg
    pd = candidate.premium_discount
    sc = candidate.score_result
    sess = candidate.session

    candles = _ohlc_from_candidate(candidate)
    last_idx = max(0, len(candles) - 1)

    # ── Structure events ──
    structure_entries: Dict[str, Any] = {}
    if struct:
        if struct.bos_detected and struct.protected_low is not None:
            structure_entries["bos"] = _structure_event(
                struct.bos_type, struct.protected_low, last_idx, "BOS")
        if struct.choch_detected:
            p = struct.protected_high if struct.choch_type == "BULLISH" else struct.protected_low
            structure_entries["choch"] = _structure_event(
                struct.choch_type, p, last_idx, "CHoCH")
        if struct.mss_detected:
            p = struct.strong_high or struct.protected_high
            structure_entries["mss"] = _structure_event(
                struct.mss_type, p, last_idx, "MSS")

    # ── Swings ──
    swings: List[Dict] = []
    if struct:
        if struct.strong_high:
            swings.append({"type": "HH", "price": struct.strong_high, "index": last_idx})
        if struct.strong_low:
            swings.append({"type": "LL", "price": struct.strong_low, "index": last_idx})

    # ── Order Blocks ──
    obs: List[Dict] = []
    if ob and ob.ob_detected:
        obs.append({
            "type": ob.ob_type,
            "top": ob.ob_top,
            "bottom": ob.ob_bottom,
            "mid": ob.ob_mid,
            "fresh": ob.fresh,
            "mitigated": ob.mitigated,
            "anchor_candle": max(0, last_idx - 5),
        })

    # ── FVGs ──
    fvgs: List[Dict] = []
    if fvg and fvg.fvg_detected:
        fvgs.append({
            "type": fvg.fvg_type,
            "top": fvg.fvg_top,
            "bottom": fvg.fvg_bottom,
            "size": fvg.fvg_size,
            "mitigated": fvg.mitigated,
            "candle": max(0, last_idx - 3),
        })

    # ── Liquidity ──
    liquidity: Dict[str, Any] = {}
    if sess:
        if sess.pdh is not None:
            liquidity["pdh"] = sess.pdh
        if sess.pdl is not None:
            liquidity["pdl"] = sess.pdl
    if liq:
        if liq.sweep_price is not None:
            liquidity["sweep_price"] = liq.sweep_price
        if liq.sweep_type:
            liquidity["sweep_type"] = liq.sweep_type

    # ── Drawing (trade setup) ──
    tp_list = _tp_ladder(candidate)

    drawing: Dict[str, Any] = {
        "buy_sell": candidate.direction,
        "entry_price": _entry_price(candidate),
        "sl_price": candidate.stop_loss,
        "tp": tp_list,
    }

    # ── Scoring ──
    scoring: Dict[str, Any] = {
        "score": candidate.score,
        "direction": candidate.direction,
        "rank": candidate.rank,
        "confidence_score": candidate.confidence_score,
        "confidence_label": candidate.confidence_label,
        "approved": candidate.approved,
        "recommendation": sc.recommendation if sc else None,
        "reasons": list(candidate.reasons),
    }

    # ── Premium / Discount zones ──
    premium_discount: Dict[str, Any] = {}
    if pd:
        premium_discount = {
            "premium_high": pd.premium_high,
            "discount_low": pd.discount_low,
            "equilibrium": pd.equilibrium,
        }

    return {
        "metadata": {
            "symbol": candidate.symbol,
            "timeframe": candidate.timeframe,
            "setup_id": candidate.setup_id,
            "session_label": (
                candidate.session.current_session.label
                if candidate.session and getattr(candidate.session, "current_session", None)
                else None
            ),
        },
        "chart": {
            "ohlc": candles,
        },
        "structure": structure_entries,
        "liquidity": liquidity,
        "session": {
            "pdh": liquidity.get("pdh"),
            "pdl": liquidity.get("pdl"),
        },
        "order_blocks": obs,
        "fvg": fvgs,
        "premium_discount": premium_discount,
        "drawing": drawing,
        "scoring": scoring,
    }


def setup_to_scene(candidate: SetupCandidate) -> Scene:
    """Convert a SetupCandidate directly to a Scene.

    Args:
        candidate: detected setup

    Returns:
        Scene ready for layout + rendering.
    """
    snapshot = setup_to_snapshot(candidate)
    return build_scene(snapshot)


# ── Helpers ──────────────────────────────────────────────────────

def _ohlc_from_candidate(candidate: SetupCandidate) -> List[Dict]:
    """Extract OHLC data from candidate."""
    chart_data = candidate.chart_data or {}
    ohlc: List[Dict] = []
    for i, row in enumerate(chart_data.get("ohlc", [])):
        if isinstance(row, dict):
            entry = dict(row)
        else:
            entry = _row_to_dict(row)
        entry["index"] = i
        ohlc.append(entry)
    return ohlc


def _structure_event(direction: Optional[str], price: Optional[float],
                     last_idx: int, label: str) -> Dict[str, Any]:
    return {
        "price": price,
        "start_index": max(0, last_idx - 3),
        "end_index": last_idx,
        "direction": direction or "NEUTRAL",
        "label": label,
    }


def _entry_price(candidate: SetupCandidate) -> Optional[float]:
    if candidate.entry_zone:
        return candidate.entry_zone.get("entry_price")
    if candidate.ob and candidate.ob.ob_detected:
        return candidate.ob.ob_mid
    if candidate.fvg and candidate.fvg.fvg_detected:
        if candidate.fvg.fvg_top and candidate.fvg.fvg_bottom:
            return (candidate.fvg.fvg_top + candidate.fvg.fvg_bottom) / 2
    return None


def _tp_ladder(candidate: SetupCandidate) -> List[float]:
    """Display-only TP ladder at 1R/2R/3R derived from Entry/SL.

    Execution levels are NOT changed — this only feeds the chart, so a
    client sees the full profit-target picture (TP1/TP2/TP3).
    """
    entry = _entry_price(candidate)
    sl = candidate.stop_loss
    if entry is None or sl is None or sl == entry:
        if candidate.take_profit is not None:
            return [candidate.take_profit]
        return []
    risk = abs(entry - sl)
    if candidate.direction == "BUY":
        return [round(entry + risk * r, 2) for r in (1, 2, 3)]
    return [round(entry - risk * r, 2) for r in (1, 2, 3)]


def _row_to_dict(row) -> Dict:
    """Convert a pandas Series or tuple to OHLC dict."""
    try:
        return {
            "open": float(getattr(row, "open", row.get("Open", 0))),
            "high": float(getattr(row, "high", row.get("High", 0))),
            "low": float(getattr(row, "low", row.get("Low", 0))),
            "close": float(getattr(row, "close", row.get("Close", 0))),
            "volume": float(getattr(row, "volume", row.get("Volume", 0))),
            "time": str(getattr(row, "time", row.get("time", ""))),
        }
    except Exception:
        return {"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0, "time": ""}
