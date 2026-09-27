"""Order Block detection anchored to BOS / CHoCH / MSS structure breaks.

Each structure event produces one OB at the last opposing candle before the break.

  Bearish BOS/CHoCH/MSS → Bullish OB (last bullish candle before break)
  Bullish BOS/CHoCH/MSS → Bearish OB (last bearish candle before break)
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def _is_bullish(candle: Dict) -> bool:
    return candle["close"] >= candle["open"]


def _find_last_opposing(candles: List[Dict], break_idx: int,
                         lookback: int = 20) -> Optional[Dict]:
    """Find the last candle in the opposite direction before `break_idx`.

    For a bearish break: find the last bullish candle.
    For a bullish break: find the last bearish candle.
    """
    # Determine direction from the break candle itself
    break_candle = None
    for c in candles:
        if c["index"] == break_idx:
            break_candle = c
            break
    if not break_candle:
        return None

    break_is_bullish = _is_bullish(break_candle)

    length = len(candles)
    start_idx = max(0, min(break_idx, length - 1) - lookback)
    max_i = min(break_idx, length - 1)
    for i in range(max_i - 1, start_idx - 1, -1):
        if i < 0 or i >= length:
            break
        c = candles[i]
        if break_is_bullish:
            # Break is bullish → look for last bearish candle
            if not _is_bullish(c):
                return c
        else:
            # Break is bearish → look for last bullish candle
            if _is_bullish(c):
                return c

    return None


def detect_obs(candles: List[Dict], swings: List[Dict],
               bos_list: Optional[List[Dict]] = None,
               choch_list: Optional[List[Dict]] = None,
               mss_list: Optional[List[Dict]] = None) -> List[Dict]:
    """Detect Order Blocks anchored to structure break events.

    Each structure event (BOS/CHoCH/MSS) produces one OB.

    Args:
        candles: full candle list
        swings: classified swings
        bos_list: scored BOS events
        choch_list: CHoCH events
        mss_list: MSS events

    Returns:
        List of OBs sorted by recency. Each OB:
        {
            "direction": "bullish" | "bearish",
            "origin_event": "BOS" | "CHoCH" | "MSS",
            "origin_candle": int,       # the break candle index
            "anchor_candle": int,       # the OB candle index
            "top": float,               # OB candle high
            "bottom": float,            # OB candle low
            "fresh": bool,              # not yet mitigated
            "touches": int,             # how many times price touched OB range
        }
    """
    obs = []

    # Collect all structure events with their type
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

    # Sort by candle index (oldest first for proper lookback)
    events.sort(key=lambda e: e[1]["candle_index"])

    for ev_type, ev in events:
        break_idx = ev["candle_index"]
        break_dir = ev["direction"]

        # The OB direction is opposite to the break
        ob_dir = "bullish" if break_dir == "bearish" else "bearish"

        # Find the last opposing candle before the break
        opposing = _find_last_opposing(candles, break_idx, lookback=20)
        if not opposing:
            continue

        # Check if this OB would overlap with existing ones (same candle ≈ same OB)
        is_dup = False
        for existing in obs:
            if abs(existing["anchor_candle"] - opposing["index"]) <= 2:
                if existing["direction"] == ob_dir:
                    is_dup = True
                    break
        if is_dup:
            continue

        obs.append({
            "direction": ob_dir,
            "origin_event": ev_type,
            "origin_candle": break_idx,
            "anchor_candle": opposing["index"],
            "top": opposing["high"],
            "bottom": opposing["low"],
            "fresh": True,
            "touches": 0,
        })

    # Sort by recency (newest first)
    obs.sort(key=lambda o: o["origin_candle"], reverse=True)
    return obs


def check_ob_mitigation(obs: List[Dict], candles: List[Dict]) -> List[Dict]:
    """Mark OBs as mitigated if price closed beyond the OB boundary.

    Bullish OB: mitigated if close below bottom.
    Bearish OB: mitigated if close above top.
    """
    for ob in obs:
        anchor = ob["anchor_candle"]
        touches = 0
        for c in candles:
            if c["index"] <= anchor:
                continue
            # Count touches
            if ob["direction"] == "bullish":
                if ob["bottom"] <= c["low"] <= ob["top"] or \
                   ob["bottom"] <= c["high"] <= ob["top"]:
                    touches += 1
                if c["low"] <= ob["bottom"] and c["close"] < ob["bottom"]:
                    ob["fresh"] = False
                    ob["mitigated_at"] = c["index"]
                    break
            else:
                if ob["bottom"] <= c["low"] <= ob["top"] or \
                   ob["bottom"] <= c["high"] <= ob["top"]:
                    touches += 1
                if c["high"] >= ob["top"] and c["close"] > ob["top"]:
                    ob["fresh"] = False
                    ob["mitigated_at"] = c["index"]
                    break
        ob["touches"] = touches
    return obs
