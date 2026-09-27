"""Fair Value Gap detection: gaps between consecutive candle bodies, linked to structure events."""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def _fvg_overlaps(fvg: Dict, candle_idx: int, max_dist: int = 3) -> bool:
    """Check if an FVG overlaps with a candle within max_dist candles."""
    # FVG spans from start_index to end_index
    # Check if structure candle is within or near the FVG range
    fvg_start = fvg.get("start_index", 0)
    fvg_end = fvg.get("end_index", 0)
    return abs(candle_idx - fvg_start) <= max_dist or \
           abs(candle_idx - fvg_end) <= max_dist or \
           (fvg_start <= candle_idx <= fvg_end)


def detect_fvgs(candles: List[Dict]) -> List[Dict]:
    """Detect FVGs between consecutive candles.

    Bullish FVG: low of candle[i+2] > high of candle[i] (gap up).
    Bearish FVG: high of candle[i+2] < low of candle[i] (gap down).

    Returns list of {start_index, end_index, top, bottom, type, mitigated}
    """
    fvgs = []
    n = len(candles)
    for i in range(n - 2):
        c0 = candles[i]
        c2 = candles[i + 2]

        # Bullish: gap up between c0 and c2
        if c2["low"] > c0["high"]:
            top = c2["low"]
            bot = c0["high"]
            if top > bot:
                fvgs.append({
                    "start_index": i,
                    "end_index": i + 2,
                    "top": top,
                    "bottom": bot,
                    "type": "bullish",
                    "mitigated": False,
                    "origin_event": None,
                    "origin_candle": None,
                })

        # Bearish: gap down between c0 and c2
        elif c2["high"] < c0["low"]:
            top = c0["low"]
            bot = c2["high"]
            if top > bot:
                fvgs.append({
                    "start_index": i,
                    "end_index": i + 2,
                    "top": top,
                    "bottom": bot,
                    "type": "bearish",
                    "mitigated": False,
                    "origin_event": None,
                    "origin_candle": None,
                })

    return fvgs


def link_fvgs_to_structure(fvgs: List[Dict],
                            bos_list: Optional[List[Dict]] = None,
                            choch_list: Optional[List[Dict]] = None,
                            mss_list: Optional[List[Dict]] = None,
                            max_distance: int = 3) -> List[Dict]:
    """Link FVGs to originating structure events (BOS/CHoCH/MSS).

    For each structure event, find a nearby FVG of the same direction.
    The FVG formed as displacement from the structure break.

    Args:
        fvgs: list from detect_fvgs()
        bos_list: scored BOS events
        choch_list: CHoCH events
        mss_list: MSS events
        max_distance: max candles between FVG and structure event

    Returns:
        FVGs with origin_event / origin_candle filled for linked ones.
    """
    # Collect all events with their type
    events = []
    if bos_list:
        for b in bos_list:
            events.append(("BOS", b))
    if choch_list:
        for c in choch_list:
            events.append(("CHoCH", c))
    if mss_list:
        for m in mss_list:
            events.append(("MSS", m))

    if not events:
        return fvgs

    # Sort by candle index (oldest first)
    events.sort(key=lambda e: e[1]["candle_index"])

    # For each event, try to find a matching FVG
    for ev_type, ev in events:
        brk_idx = ev["candle_index"]
        brk_dir = ev["direction"]

        # Find best FVG match: same direction, closest to break candle
        best_fvg = None
        best_dist = 999
        for fvg in fvgs:
            # Skip if already linked to a different event
            if fvg["origin_event"] is not None:
                continue
            if fvg["type"] != brk_dir:
                continue
            # FVG spans start_index..end_index; break candle should be nearby
            dist = min(abs(brk_idx - fvg["start_index"]),
                       abs(brk_idx - fvg["end_index"]),
                       abs(brk_idx - (fvg["start_index"] + 1)))
            if dist <= max_distance and dist < best_dist:
                best_fvg = fvg
                best_dist = dist

        if best_fvg:
            best_fvg["origin_event"] = ev_type
            best_fvg["origin_candle"] = brk_idx

    return fvgs


def check_fvg_mitigation(fvgs: List[Dict], candles: List[Dict]) -> List[Dict]:
    """Mark FVGs as mitigated if price retraced and filled the gap."""
    for fvg in fvgs:
        end = fvg["end_index"]
        for c in candles:
            if c["index"] <= end:
                continue
            if fvg["type"] == "bullish":
                if c["low"] <= fvg["top"] and c["high"] >= fvg["bottom"]:
                    fvg["mitigated"] = True
                    fvg["filled_at"] = c["index"]
                    break
            else:
                if c["high"] >= fvg["bottom"] and c["low"] <= fvg["top"]:
                    fvg["mitigated"] = True
                    fvg["filled_at"] = c["index"]
                    break
    return fvgs
