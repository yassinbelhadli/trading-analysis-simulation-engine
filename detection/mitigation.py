"""Unified Mitigation Engine — tracks mitigation/touches/invalidation for any zone (OB or FVG).

Every zone follows the same lifecycle:

    Created → Active (price hasn't violated zone)
             → Touched (price entered zone range, no close beyond)
             → Mitigated (price closed beyond zone boundary)
             → Invalidated (zone expired / price moved too far)

Zones from different detection modules (order_block, fvg) share identical fields.
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Max candles before a zone is considered expired
MAX_ZONE_AGE = 50
# How far price can be from zone before it's considered irrelevant (in ATR-like terms)
MAX_DISTANCE_MULT = 3.0


def build_zones(obs: List[Dict], fvgs: List[Dict]) -> List[Dict]:
    """Normalize OB and FVG lists into a unified zone list.

    Each zone:
        type: "OB" | "FVG"
        direction: "bullish" | "bearish"
        top: float
        bottom: float
        anchor_candle: int   # candle that defines the zone
        start_index: int     # first candle of zone
        end_index: int       # last candle of zone
        origin_event: str | None
        origin_candle: int | None
        fresh: bool
        mitigated: bool
        mitigated_at: int | None
        touches: int
        invalidated: bool
    """
    zones = []

    for ob in obs:
        zones.append({
            "type": "OB",
            "direction": ob["direction"],
            "top": ob["top"],
            "bottom": ob["bottom"],
            "anchor_candle": ob["anchor_candle"],
            "start_index": ob["anchor_candle"],
            "end_index": ob["anchor_candle"],
            "origin_event": ob.get("origin_event"),
            "origin_candle": ob.get("origin_candle"),
            "fresh": True,
            "mitigated": not ob.get("fresh", True),
            "mitigated_at": ob.get("mitigated_at"),
            "touches": ob.get("touches", 0),
            "invalidated": False,
        })

    for fvg in fvgs:
        zones.append({
            "type": "FVG",
            "direction": fvg["type"],
            "top": fvg["top"],
            "bottom": fvg["bottom"],
            "anchor_candle": fvg["end_index"],
            "start_index": fvg["start_index"],
            "end_index": fvg["end_index"],
            "origin_event": fvg.get("origin_event"),
            "origin_candle": fvg.get("origin_candle"),
            "fresh": True,
            "mitigated": fvg.get("mitigated", False),
            "mitigated_at": fvg.get("filled_at"),
            "touches": fvg.get("touches", 0),
            "invalidated": False,
        })

    return zones


def scan_zones(zones: List[Dict], candles: List[Dict]) -> List[Dict]:
    """Unified scan over all zones.

    For each candle after a zone:
      - Count touches (price enters zone range)
      - Mark mitigated (price closes beyond zone boundary)
      - Mark invalidated (zone too old or price too far)

    Args:
        zones: list from build_zones()
        candles: full candle list

    Returns:
        Updated zones with fresh/mitigated/touches/invalidated populated.
    """
    if not zones or not candles:
        return zones

    # Estimate average candle range for distance-based invalidation
    recent = candles[-50:] if len(candles) >= 50 else candles
    avg_range = sum(c["high"] - c["low"] for c in recent) / len(recent)

    for zone in zones:
        anchor = zone["anchor_candle"]
        zone_top = zone["top"]
        zone_bot = zone["bottom"]
        direction = zone["direction"]

        touches = 0
        found_mitigation = None

        for c in candles:
            # Skip candles up to and including the zone anchor
            if c["index"] <= anchor:
                continue

            # --- Touches ---
            # Price entered the zone range
            touched = False
            if direction == "bullish":
                if c["low"] <= zone_top and c["high"] >= zone_bot:
                    touched = True
            else:
                if c["high"] >= zone_bot and c["low"] <= zone_top:
                    touched = True

            if touched:
                touches += 1

            # --- Mitigation ---
            # Bullish zone: mitigated if close below bottom
            # Bearish zone: mitigated if close above top
            if direction == "bullish":
                if c["close"] < zone_bot:
                    found_mitigation = c["index"]
                    break
            else:
                if c["close"] > zone_top:
                    found_mitigation = c["index"]
                    break

            # --- Invalidation (distance) ---
            # If price moved far from zone without touching it, zone is likely dead
            dist_from_zone = 0
            if direction == "bullish":
                # Price should be near the zone; if far above, zone may have been skipped
                if c["low"] > zone_top + avg_range * MAX_DISTANCE_MULT:
                    if not touched:
                        zone["invalidated"] = True
                        zone["invalidated_at"] = c["index"]
                        break
            else:
                if c["high"] < zone_bot - avg_range * MAX_DISTANCE_MULT:
                    if not touched:
                        zone["invalidated"] = True
                        zone["invalidated_at"] = c["index"]
                        break

        # --- Age invalidation ---
        # Zone too old without being mitigated
        latest_idx = candles[-1]["index"]
        if found_mitigation is None and not zone["invalidated"]:
            age = latest_idx - anchor
            if age > MAX_ZONE_AGE:
                zone["invalidated"] = True
                zone["invalidated_at"] = latest_idx

        zone["fresh"] = touches == 0 and found_mitigation is None and not zone["invalidated"]
        zone["touches"] = touches
        zone["mitigated"] = found_mitigation is not None
        zone["mitigated_at"] = found_mitigation

        # Derive entry-ready status: price touched zone but hasn't mitigated it
        zone["active"] = (touches > 0 and found_mitigation is None and not zone["invalidated"])

    return zones


def filter_active_zones(zones: List[Dict], max_count: int = 5) -> List[Dict]:
    """Return zones that are realistic entry candidates.

    Priority:
      1. Active (touched but not mitigated, not invalidated)
      2. Fresh (not yet touched, not mitigated, not invalidated)
      3. Recent (newest first)
    """
    active = [z for z in zones if z.get("active")]
    fresh = [z for z in zones if z["fresh"]]
    # Exclude mitigated / invalidated
    alive = [z for z in zones if not z["mitigated"] and not z["invalidated"]]

    # Sort active + fresh by recency
    candidates = sorted(active + fresh, key=lambda z: z["anchor_candle"], reverse=True)
    if not candidates:
        # Fallback: alive zones sorted by recency
        candidates = sorted(alive, key=lambda z: z["anchor_candle"], reverse=True)
    return candidates[:max_count]
