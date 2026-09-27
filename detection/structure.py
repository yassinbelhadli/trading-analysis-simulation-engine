"""BOS / CHoCH / MSS detection from swing structure.

Scans entire candle history for ALL structure breaks.
The engine selects the latest for signal production.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

_MIN_DISPLACEMENT = 0.0005  # 0.05% minimum break displacement


def _find_trend(swings: List[Dict], count: int = 4) -> tuple:
    """Determine recent trend direction and strength."""
    classified = [s for s in swings if s["type"] in ("HH", "LH", "HL", "LL")]
    if len(classified) < count:
        return None, 0
    recent = classified[-count:]
    highs = [s for s in recent if s["type"] in ("HH", "LH")]
    lows = [s for s in recent if s["type"] in ("HL", "LL")]

    if len(highs) < 2 or len(lows) < 2:
        return None, 0

    bullish_h = all(highs[i]["price"] > highs[i-1]["price"] for i in range(1, len(highs)))
    bullish_l = all(lows[i]["price"] > lows[i-1]["price"] for i in range(1, len(lows)))
    bearish_h = all(highs[i]["price"] < highs[i-1]["price"] for i in range(1, len(highs)))
    bearish_l = all(lows[i]["price"] < lows[i-1]["price"] for i in range(1, len(lows)))

    if bullish_h and bullish_l:
        return "bullish", min(len(highs), len(lows))
    if bearish_h and bearish_l:
        return "bearish", min(len(highs), len(lows))
    return None, 0


def detect_bos(swings: List[Dict], candles: List[Dict]) -> List[Dict]:
    """Break of Structure — scan all swings for breaks throughout history.

    Bullish BOS: close breaks above the most recent significant swing high.
    Bearish BOS: close breaks below the most recent significant swing low.

    Iterates over ALL classified swings; returns all BOS events across history.
    The engine selects the latest for the final signal.
    """
    results = []
    classified = [s for s in swings if s["type"] in ("HH", "LH", "HL", "LL")]

    # Group into pairs of (swing_high, swing_low) as they alternate in time
    # Process each swing high: check if it gets broken later
    for i, swing in enumerate(classified):
        if swing["type"] in ("HH", "LH"):
            # Check if any later candle breaks above this high
            for c in candles:
                if c["index"] <= swing["index"]:
                    continue
                if c["close"] > swing["price"] * (1 + _MIN_DISPLACEMENT):
                    disp = (c["close"] - swing["price"]) / swing["price"] * 100
                    results.append({
                        "candle_index": c["index"],
                        "price": swing["price"],
                        "direction": "bullish",
                        "swing_index": swing["index"],
                        "swing_type": swing["type"],
                        "displacement_pct": round(disp, 3),
                    })
                    break

        if swing["type"] in ("HL", "LL"):
            for c in candles:
                if c["index"] <= swing["index"]:
                    continue
                if c["close"] < swing["price"] * (1 - _MIN_DISPLACEMENT):
                    disp = (swing["price"] - c["close"]) / swing["price"] * 100
                    results.append({
                        "candle_index": c["index"],
                        "price": swing["price"],
                        "direction": "bearish",
                        "swing_index": swing["index"],
                        "swing_type": swing["type"],
                        "displacement_pct": round(disp, 3),
                    })
                    break

    return results


def detect_choch(swings: List[Dict], candles: List[Dict]) -> List[Dict]:
    """Change of Character — trend reversal after trending moves."""
    results = []
    classified = [s for s in swings if s["type"] in ("HH", "LH", "HL", "LL")]

    # Scan from the beginning: for each window of 5+ swings, check if a reversal happens
    for i in range(4, len(classified)):
        window = classified[:i+1]
        trend, strength = _find_trend(window, 4)
        if not trend or strength < 2:
            continue

        last = classified[i]
        if trend == "bearish":
            # In a bearish structure, a bullish CHoCH is when price breaks above
            # the most recent LH (lower high)
            if last["type"] in ("HH", "LH"):
                # Check if close breaks above it
                for c in candles:
                    if c["index"] <= last["index"]:
                        continue
                    if c["close"] > last["price"] * (1 + _MIN_DISPLACEMENT):
                        disp = (c["close"] - last["price"]) / last["price"] * 100
                        # But only count this if it breaks above the last high meaningfully
                        # (it should exceed the previous high too)
                        prev_high = None
                        for s2 in reversed(classified[:i]):
                            if s2["type"] in ("HH", "LH"):
                                prev_high = s2
                                break
                        if prev_high and c["close"] > prev_high["price"]:
                            results.append({
                                "candle_index": c["index"],
                                "price": last["price"],
                                "direction": "bullish",
                                "swing_index": last["index"],
                                "displacement_pct": round(disp, 3),
                            })
                            break

        elif trend == "bullish":
            if last["type"] in ("HL", "LL"):
                for c in candles:
                    if c["index"] <= last["index"]:
                        continue
                    if c["close"] < last["price"] * (1 - _MIN_DISPLACEMENT):
                        disp = (last["price"] - c["close"]) / last["price"] * 100
                        prev_low = None
                        for s2 in reversed(classified[:i]):
                            if s2["type"] in ("HL", "LL"):
                                prev_low = s2
                                break
                        if prev_low and c["close"] < prev_low["price"]:
                            results.append({
                                "candle_index": c["index"],
                                "price": last["price"],
                                "direction": "bearish",
                                "swing_index": last["index"],
                                "displacement_pct": round(disp, 3),
                            })
                            break

    return results


def detect_mss(swings: List[Dict], candles: List[Dict]) -> List[Dict]:
    """Market Structure Shift = CHoCH + confirmation swing in new direction."""
    choch_list = detect_choch(swings, candles)
    if not choch_list:
        return []

    classified = [s for s in swings if s["type"] in ("HH", "LH", "HL", "LL")]
    if not classified:
        return []

    ms = []
    for choch in choch_list:
        # Find confirmation: a swing after the CHoCH that aligns with the new trend
        for s in classified:
            if s["index"] <= choch["candle_index"]:
                continue
            if choch["direction"] == "bullish":
                if s["type"] in ("HL", "HH"):
                    ms.append(choch)
                    break
            else:  # bearish
                if s["type"] in ("LH", "LL"):
                    ms.append(choch)
                    break
        else:
            # No confirmation swing found — still add CHoCH as potential MSS
            ms.append(choch)

    return ms
