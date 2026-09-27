"""Swing High / Low detection and HH/HL/LH/LL classification."""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Default lookback — can be patched for stability tests
LOOKBACK = 5


def detect_swings(candles: List[Dict], lookback: int = None) -> List[Dict]:
    if lookback is None:
        lookback = LOOKBACK
    """Find swing highs and lows using local max/min with lookback.

    Each swing: {type, price, index, high, low}
    type: 'swing_high' or 'swing_low'
    """
    swings = []
    n = len(candles)
    for i in range(lookback, n - lookback):
        c = candles[i]
        # Swing high: high is higher than lookback neighbours on both sides
        is_high = True
        for j in range(i - lookback, i + lookback + 1):
            if j == i:
                continue
            if candles[j]["high"] >= c["high"]:
                is_high = False
                break
        if is_high:
            swings.append({"type": "swing_high", "price": c["high"],
                           "index": i, "high": c["high"], "low": c["low"]})
            continue

        # Swing low: low is lower than lookback neighbours on both sides
        is_low = True
        for j in range(i - lookback, i + lookback + 1):
            if j == i:
                continue
            if candles[j]["low"] <= c["low"]:
                is_low = False
                break
        if is_low:
            swings.append({"type": "swing_low", "price": c["low"],
                           "index": i, "high": c["high"], "low": c["low"]})
    return swings


def classify_swings(swings: List[Dict]) -> List[Dict]:
    """Classify swings as HH/HL/LH/LL.

    HH: higher high than previous high
    HL: higher low than previous low
    LH: lower high than previous high
    LL: lower low than previous low
    """
    if len(swings) < 2:
        return swings

    classified = [swings[0]]
    prev_high = None
    prev_low = None

    for i in range(len(swings)):
        s = dict(swings[i])
        if s["type"] == "swing_high":
            if prev_high is None:
                s["type"] = "HH"
            elif s["price"] > prev_high:
                s["type"] = "HH"
            else:
                s["type"] = "LH"
            prev_high = s["price"]
        else:
            if prev_low is None:
                s["type"] = "LL"
            elif s["price"] < prev_low:
                s["type"] = "LL"
            else:
                s["type"] = "HL"
            prev_low = s["price"]
        classified.append(s)

    return classified


def latest_swing_highs(swings: List[Dict], count: int = 2) -> List[Dict]:
    """Return the last `count` HH/LH swings."""
    highs = [s for s in swings if s["type"] in ("HH", "LH")]
    return highs[-count:] if len(highs) >= count else highs


def latest_swing_lows(swings: List[Dict], count: int = 2) -> List[Dict]:
    """Return the last `count` HL/LL swings."""
    lows = [s for s in swings if s["type"] in ("HL", "LL")]
    return lows[-count:] if len(lows) >= count else lows
