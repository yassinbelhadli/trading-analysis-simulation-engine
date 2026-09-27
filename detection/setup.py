"""Setup Finder — selects the best trade setup from engine + scoring output.

Picks the strongest active zone (OB or FVG) aligned with the score direction
and wraps it into a TradeSetup for the Entry Engine to evaluate.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Min score to consider a tradeable setup
MIN_SETUP_SCORE = 60


def find_best_setup(result: Dict) -> Optional[Dict]:
    """Find the best trade setup from an engine analysis result.

    Logic:
      1. Scoring must be >= 60 (setup or high_confidence).
      2. Direction must be clear (bullish or bearish).
      3. Find an active zone (OB or FVG) aligned with direction.
      4. Prefer OB over FVG if both active (OB is stronger).
      5. Return TradeSetup dict or None.

    Args:
        result: dict from engine.analyze()

    Returns:
        TradeSetup dict with:
            score, classification, direction, confidence,
            origin_event, origin_candle,
            trigger_zone, sweep, signal, reasons
        or None if no viable setup.
    """
    scoring = result.get("scoring")
    if not scoring:
        return None

    score = scoring.get("score", 0)
    classification = scoring.get("classification", "ignore")
    direction = scoring.get("direction", "neutral")

    if score < MIN_SETUP_SCORE:
        logger.debug("Setup rejected: score %d < %d", score, MIN_SETUP_SCORE)
        return None
    if direction == "neutral":
        logger.debug("Setup rejected: neutral direction")
        return None

    # Find best trigger zone (active OB or FVG aligned with direction)
    zones = result.get("zones", [])
    trigger_zone = _select_trigger_zone(zones, direction)

    if not trigger_zone:
        logger.debug("Setup rejected: no active zone for %s", direction)
        return None

    # Determine origin event from zone or latest structure event
    origin_event = trigger_zone.get("origin_event", "?")
    origin_candle = trigger_zone.get("origin_candle", 0)

    # Collect reasons
    reasons = []
    if scoring.get("signal"):
        reasons.append(scoring["signal"])
    if trigger_zone:
        reasons.append("%s %s zone @%d" % (
            trigger_zone["direction"], trigger_zone["type"],
            trigger_zone["anchor_candle"]))
    sweep_type = result.get("sweep_type")
    if sweep_type:
        reasons.append("%s sweep" % sweep_type)

    confidence = score / 100.0

    # Build the trigger zone with entry/SL calculation hints
    entry_hint = _entry_from_zone(trigger_zone, direction)

    trade_setup = {
        "score": score,
        "classification": classification,
        "direction": direction,
        "confidence": confidence,
        "origin_event": origin_event,
        "origin_candle": origin_candle,
        "trigger_zone": trigger_zone,
        "entry_hint": entry_hint,
        "sweep_type": sweep_type,
        "signal": scoring.get("signal", ""),
        "reasons": reasons,
    }

    logger.info("Setup found: %s %s (score=%d, zone=%s %s)",
                direction, classification, score,
                trigger_zone["type"], trigger_zone.get("anchor_candle", "?"))
    return trade_setup


def _select_trigger_zone(zones: List[Dict], direction: str) -> Optional[Dict]:
    """Pick the best active zone aligned with `direction`.

    Priority:
      1. Active OB in same direction
      2. Active FVG in same direction
      3. Fresh OB in same direction
      4. Fresh FVG in same direction
    """
    if not zones:
        return None

    candidates = [z for z in zones if z.get("direction") == direction
                  and not z.get("mitigated") and not z.get("invalidated")]

    def _priority(z):
        """Lower number = higher priority."""
        is_active = 1 if z.get("active") else (2 if z.get("fresh") else 3)
        is_ob = 0 if z["type"] == "OB" else 1
        return (is_active, is_ob)

    candidates.sort(key=_priority)
    return candidates[0] if candidates else None


def _entry_from_zone(zone: Dict, direction: str) -> Dict:
    """Calculate entry/SL hints from a zone.

    For bullish (BUY):
        Ideal entry: near zone BOTTOM (buying support)
        SL: below zone bottom with 0.2 % buffer

    For bearish (SELL):
        Ideal entry: near zone TOP (selling resistance)
        SL: above zone top with 0.2 % buffer
    """
    top = zone.get("top", 0)
    bottom = zone.get("bottom", 0)

    if direction == "bullish":
        return {
            "entry_price": bottom,
            "stop_loss": bottom * 0.998,
            "direction": "BUY",
        }
    elif direction == "bearish":
        return {
            "entry_price": top,
            "stop_loss": top * 1.002,
            "direction": "SELL",
        }
    return {"entry_price": 0, "stop_loss": 0, "direction": "NONE"}
