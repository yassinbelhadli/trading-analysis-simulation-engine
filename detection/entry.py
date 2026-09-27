"""Entry Engine — evaluates a TradeSetup against live price and emits EntrySignal.

The engine does NOT calculate lot sizes or risk. It only answers:

    1. Is there an active zone at a reasonable price?
    2. Is the setup still valid?
    3. Has the zone been retested?
    4. Should we enter now (market) or wait (limit)?

Output is an EntrySignal consumed by the Risk Manager / Trade Manager.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Price must be within this % of the zone to consider it "at the zone"
ZONE_PROXIMITY_PCT = 0.002  # 0.2 %
# Max candles since zone creation for entry relevance
MAX_ZONE_AGE_CANDLES = 30
# Default risk/reward ratio for TP calculation
RR_RATIO = 2.0


def evaluate_setup(setup: Dict, candles: List[Dict]) -> Dict:
    """Evaluate a TradeSetup against current price data.

    Args:
        setup: dict from setup.find_best_setup()
        candles: full candle list (for retest detection)

    Returns:
        EntrySignal dict:
            valid: bool
            direction: str
            entry_type: "MARKET" | "LIMIT" | "NONE"
            entry_price: float
            stop_loss: float
            take_profit: float
            risk_reward: float
            zone: dict (the trigger zone)
            reason: str
            setup_score: int
            confidence: float
    """
    if not setup or not candles:
        return _invalid("No setup or no candles")

    direction = setup.get("direction", "neutral")
    trigger_zone = setup.get("trigger_zone")
    entry_hint = setup.get("entry_hint", {})

    if not trigger_zone or not entry_hint:
        return _invalid("No trigger zone or entry hint")

    if direction == "neutral":
        return _invalid("Neutral direction")

    zone_top = trigger_zone.get("top", 0)
    zone_bot = trigger_zone.get("bottom", 0)
    anchor = trigger_zone.get("anchor_candle", 0)

    # --- Check zone age ---
    latest_idx = candles[-1]["index"]
    if latest_idx - anchor > MAX_ZONE_AGE_CANDLES:
        return _invalid("Zone too old (%d candles)" % (latest_idx - anchor))

    # --- Check zone life status ---
    if trigger_zone.get("mitigated"):
        return _invalid("Zone already mitigated")
    if trigger_zone.get("invalidated"):
        return _invalid("Zone invalidated")

    # --- Find current price ---
    latest = candles[-1]
    current_price = latest["close"]

    # --- Determine entry price and SL from setup hints ---
    trade_dir = entry_hint.get("direction", "BUY")
    stop_loss = entry_hint.get("stop_loss", 0)

    if trade_dir == "BUY":
        ideal_entry = zone_bot
    else:
        ideal_entry = zone_top

    # --- Check if price is near/inside the zone ---
    at_zone, proximity = _price_at_zone(current_price, zone_top, zone_bot, direction)

    # --- Check price proximity to ideal entry ---
    dist_to_ideal = abs(current_price - ideal_entry)
    zone_range = zone_top - zone_bot if zone_top > zone_bot else 1
    near_ideal = dist_to_ideal < zone_range * ZONE_PROXIMITY_PCT * 2

    # --- Check for retest confirmation candles ---
    retest = _detect_retest(trigger_zone, candles)

    # --- Determine entry type ---
    if at_zone and near_ideal and retest["confirmed"]:
        # Price is at ideal entry point and retest confirmed: market entry
        entry_type = "MARKET"
        entry_price = current_price
        reason = "Retest confirmed at zone"
    elif at_zone and retest["confirmed"]:
        # Retest confirmed but price not at ideal point: limit entry
        entry_type = "LIMIT"
        entry_price = ideal_entry
        reason = "Retest confirmed, entering at ideal zone price"
    elif at_zone:
        # Price at zone but no retest yet: limit entry, wait for confirmation
        entry_type = "LIMIT"
        entry_price = ideal_entry
        reason = "Price at zone, waiting for retest confirmation"
    else:
        # Price is away from zone: no entry
        entry_type = "NONE"
        entry_price = 0
        reason = "Price %s from zone (%.2f%%)" % (
            "above" if current_price > zone_top else "below",
            proximity * 100)

    # --- Calculate basic TP via R:R ---
    if entry_type != "NONE" and stop_loss and entry_price:
        sl_distance = abs(entry_price - stop_loss)
        default_rr = RR_RATIO
        if trade_dir == "BUY":
            take_profit = entry_price + (sl_distance * default_rr)
        else:
            take_profit = entry_price - (sl_distance * default_rr)
        risk_reward = sl_distance / (abs(entry_price - take_profit) + 1)
        risk_reward = default_rr  # fixed until risk manager handles TP
    else:
        take_profit = 0.0
        risk_reward = 0.0

    score = setup.get("score", 0)
    confidence = setup.get("confidence", 0.0)

    signal = {
        "valid": entry_type != "NONE",
        "direction": trade_dir,
        "entry_type": entry_type,
        "entry_price": round(entry_price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "risk_reward": round(risk_reward, 2),
        "zone": trigger_zone,
        "reason": reason,
        "setup_score": score,
        "confidence": confidence,
        "proximity": round(proximity * 100, 2),
        "retest_confirmed": retest["confirmed"],
        "retest_candles": retest["count"],
    }

    logger.info("EntrySignal: %s %s price=%.2f sl=%.2f tp=%.2f [%s]",
                trade_dir, entry_type, entry_price, stop_loss,
                take_profit, reason)
    return signal


def _price_at_zone(price: float, zone_top: float, zone_bot: float,
                   direction: str) -> tuple:
    """Check if price is near the zone.

    For bullish: price should be near the zone BOTTOM (buying the dip).
    For bearish: price should be near the zone TOP (selling the rip).

    Returns (at_zone: bool, proximity_pct: float).
    """
    zone_range = zone_top - zone_bot if zone_top > zone_bot else 1

    if direction == "bullish":
        # Price should be near the zone bottom (buying support)
        dist = abs(price - zone_bot)
        proximity = dist / zone_range
        at_zone = price <= zone_top and price >= zone_bot * 0.995
    else:
        # Price should be near the zone top (selling resistance)
        dist = abs(price - zone_top)
        proximity = dist / zone_range
        at_zone = price >= zone_bot and price <= zone_top * 1.005

    return at_zone, proximity


def _detect_retest(zone: Dict, candles: List[Dict]) -> Dict:
    """Check if price retested the zone since it was created.

    A retest is a candle that entered the zone range and showed rejection
    (opposite-direction close relative to the zone).

    Retest = price enters zone, then closes back in the original direction.
    """
    anchor = zone.get("anchor_candle", 0)
    zone_top = zone.get("top", 0)
    zone_bot = zone.get("bottom", 0)
    zone_dir = zone.get("direction", "bullish")

    count = 0
    confirmed = False
    last_rejection = None

    for c in candles:
        if c["index"] <= anchor:
            continue

        # Check if candle entered the zone
        entered = False
        if zone_dir == "bullish":
            # Bullish zone: entry is when price dips into zone
            if c["low"] <= zone_top and c["high"] >= zone_bot:
                entered = True
        else:
            # Bearish zone: entry is when price rallies into zone
            if c["high"] >= zone_bot and c["low"] <= zone_top:
                entered = True

        if entered:
            count += 1
            # Check rejection: close in opposite direction of entry
            # Bullish zone: price entered, close should be bullish (rejection down)
            # Bearish zone: price entered, close should be bearish (rejection up)
            is_bullish_candle = c["close"] >= c["open"]
            if zone_dir == "bullish" and is_bullish_candle:
                confirmed = True
                last_rejection = c["index"]
                break
            elif zone_dir == "bearish" and not is_bullish_candle:
                confirmed = True
                last_rejection = c["index"]
                break

    return {
        "confirmed": confirmed,
        "count": count,
        "last_rejection": last_rejection,
    }


def _invalid(reason: str) -> Dict:
    logger.debug("Entry rejected: %s", reason)
    return {
        "valid": False,
        "direction": "NONE",
        "entry_type": "NONE",
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "risk_reward": 0.0,
        "zone": None,
        "reason": reason,
        "setup_score": 0,
        "confidence": 0.0,
        "proximity": 0.0,
        "retest_confirmed": False,
        "retest_candles": 0,
    }
