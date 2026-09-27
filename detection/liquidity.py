"""Liquidity detection — sweeps, equal highs/lows, linked to structure breaks."""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def _find_equal_clusters(swings: List[Dict], threshold_pct: float = 0.03) -> List[Dict]:
    """Find clusters of swing highs (or lows) at similar price levels.

    A cluster is 2+ swings within `threshold_pct` of each other.
    These represent liquidity pools in ICT.
    """
    if len(swings) < 2:
        return []

    clusters = []
    used = set()
    for i in range(len(swings)):
        if i in used:
            continue
        cluster = [swings[i]]
        for j in range(i + 1, len(swings)):
            if j in used:
                continue
            diff = abs(swings[i]["price"] - swings[j]["price"]) / swings[i]["price"] * 100
            if diff <= threshold_pct:
                cluster.append(swings[j])
                used.add(j)
        if len(cluster) >= 2:
            used.add(i)
            avg_price = sum(s["price"] for s in cluster) / len(cluster)
            clusters.append({
                "price": round(avg_price, 2),
                "count": len(cluster),
                "indices": [s["index"] for s in sorted(cluster, key=lambda x: x["index"])],
                "type": cluster[0]["type"] if cluster[0]["type"] in ("HH", "LH") else "HL",
            })

    return clusters


def detect_sweep(candles: List[Dict], swings: List[Dict],
                 bos_list: Optional[List[Dict]] = None) -> Dict:
    """Detect liquidity sweeps (BSL/SSL) with optional BOS linking.

    BSL (Buy Side Liquidity): price pushes above a swing high, then closes below.
    SSL (Sell Side Liquidity): price pushes below a swing low, then closes above.

    Returns dict with sweep details or empty dict.
    """
    classified = [s for s in swings if s["type"] in ("HH", "LH", "HL", "LL")]
    if not classified:
        return {}

    # Index BOS by candle for linking
    bos_candles = set()
    bos_by_candle = {}
    if bos_list:
        for b in bos_list:
            bos_candles.add(b["candle_index"])
            bos_by_candle[b["candle_index"]] = b

    result = {}

    # Check ALL swing highs for BSL sweeps
    highs = [s for s in classified if s["type"] in ("HH", "LH")]
    for high in reversed(highs):  # newest first
        after = [c for c in candles if c["index"] > high["index"]]
        if not after:
            continue
        max_after = max(c["high"] for c in after)
        close_after = after[-1]["close"]
        # Price broke above then closed back below
        if max_after > high["price"] * 1.001 and close_after < high["price"]:
            result = {
                "sweep_price": high["price"],
                "sweep_type": "BSL",
                "sweep_swing_index": high["index"],
                "sweep_swing_type": high["type"],
            }
            # Link to BOS if one happened within 5 candles after sweep
            for b_idx in sorted(bos_candles):
                if high["index"] < b_idx <= max(c["index"] for c in after):
                    if b_idx - high["index"] <= 10:
                        result["linked_bos_candle"] = b_idx
                        result["linked_bos_direction"] = bos_by_candle[b_idx]["direction"]
                        result["linked_bos_score"] = bos_by_candle[b_idx].get("score")
                        break
            break

    # Check ALL swing lows for SSL sweeps
    if not result:
        lows = [s for s in classified if s["type"] in ("HL", "LL")]
        for low in reversed(lows):
            after = [c for c in candles if c["index"] > low["index"]]
            if not after:
                continue
            min_after = min(c["low"] for c in after)
            close_after = after[-1]["close"]
            if min_after < low["price"] * 0.999 and close_after > low["price"]:
                result = {
                    "sweep_price": low["price"],
                    "sweep_type": "SSL",
                    "sweep_swing_index": low["index"],
                    "sweep_swing_type": low["type"],
                }
                for b_idx in sorted(bos_candles):
                    if low["index"] < b_idx <= max(c["index"] for c in after):
                        if b_idx - low["index"] <= 10:
                            result["linked_bos_candle"] = b_idx
                            result["linked_bos_direction"] = bos_by_candle[b_idx]["direction"]
                            result["linked_bos_score"] = bos_by_candle[b_idx].get("score")
                            break
                break

    return result


def detect_equal_highs_lows(swings: List[Dict]) -> Dict:
    """Detect liquidity clusters (equal highs/lows).

    Returns:
    {
        "equal_highs": [{"price", "count", "indices", "last_index"}, ...],
        "equal_lows": [{"price", "count", "indices", "last_index"}, ...],
    }
    """
    classified = [s for s in swings if s["type"] in ("HH", "LH", "HL", "LL")]

    swing_highs = [s for s in classified if s["type"] in ("HH", "LH")]
    swing_lows = [s for s in classified if s["type"] in ("HL", "LL")]

    return {
        "equal_highs": _find_equal_clusters(swing_highs),
        "equal_lows": _find_equal_clusters(swing_lows),
    }


def get_pdh_pdl(candles: List[Dict], swings: List[Dict]) -> dict:
    """Get Previous Day High / Low from visible data."""
    if len(candles) < 2:
        return {}
    day = candles[:96]
    return {"pdh": max(c["high"] for c in day), "pdl": min(c["low"] for c in day)}
