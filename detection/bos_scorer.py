"""BOS scoring system — independent multi-factor scoring, 0-100 scale."""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def _calc_body(candle: Dict) -> float:
    return abs(candle["close"] - candle["open"])


def _calc_atr(candles: List[Dict], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(len(candles) - period, len(candles)):
        c = candles[i]
        if i == 0:
            trs.append(c["high"] - c["low"])
        else:
            prev = candles[i - 1]
            tr = max(c["high"] - c["low"],
                     abs(c["high"] - prev["close"]),
                     abs(c["low"] - prev["close"]))
            trs.append(tr)
    return sum(trs) / len(trs) if trs else 0.0


def classify_bos(bos_events: List[Dict], swings: List[Dict],
                 candles: List[Dict]) -> List[Dict]:
    """Classify BOS events using independent multi-factor scoring (0–100).

    Scoring breakdown (total = 100):
      Close beyond swing           +20
      Body fully beyond swing      +10
      Strong displacement candle   +15
      Displacement %                +5 / +10 / +15
      External / Internal           +15 / +5
      ATR expansion                +10
      Distance from prev BOS       +5
      Volume confirmation          +5 (when volume dips below avg before BOS)
      —————————————————————————————
      Total                       100

    Classification:
      0–39   Ignore
      40–59  Weak BOS
      60–79  Good BOS
      80–100 Strong BOS
    """
    if not bos_events or len(candles) < 20:
        return bos_events

    # Pre-calc averages
    recent_candles = candles[-50:]
    avg_body = sum(_calc_body(c) for c in recent_candles) / len(recent_candles)
    avg_volume = sum(c["volume"] for c in recent_candles) / len(recent_candles)
    atr = _calc_atr(candles)

    # Swing extremes for External/Internal classification
    classified = [s for s in swings if s["type"] in ("HH", "LH", "HL", "LL")]
    top_high = max(s["price"] for s in classified) if classified else None
    bottom_low = min(s["price"] for s in classified) if classified else None

    # Sort BOS events chronologically for distance calculation
    sorted_bos = sorted(bos_events, key=lambda b: b["candle_index"])
    prev_break_idx = -999

    for event in sorted_bos:
        score = 0
        breakdown = {}

        swing_price = event["price"]

        # Find the break candle
        break_candle = None
        event_close = None
        for c in candles:
            if c["index"] == event["candle_index"]:
                break_candle = c
                event_close = c["close"]
                break

        if break_candle is None:
            continue

        # ── C1: Close beyond swing (+20) ──
        if event["direction"] == "bullish" and event_close > swing_price:
            score += 20
            breakdown["close_beyond"] = 20
        elif event["direction"] == "bearish" and event_close < swing_price:
            score += 20
            breakdown["close_beyond"] = 20
        else:
            breakdown["close_beyond"] = 0

        # ── C2: Body fully beyond swing (+10) ──
        # Entire candle body sits beyond the swing price level
        if event["direction"] == "bullish":
            body_low = min(break_candle["open"], break_candle["close"])
            if body_low > swing_price:
                score += 10
                breakdown["body_beyond"] = 10
            else:
                breakdown["body_beyond"] = 0
        else:
            body_high = max(break_candle["open"], break_candle["close"])
            if body_high < swing_price:
                score += 10
                breakdown["body_beyond"] = 10
            else:
                breakdown["body_beyond"] = 0

        # ── C3: Strong displacement candle (+15) ──
        body = _calc_body(break_candle)
        if avg_body > 0 and body >= avg_body * 1.5:
            score += 15
            breakdown["strong_candle"] = 15
        elif avg_body > 0 and body >= avg_body * 1.0:
            score += 8
            breakdown["strong_candle"] = 8
        else:
            breakdown["strong_candle"] = 0

        # ── C4: Displacement percentage (+5 / +10 / +15) ──
        disp = abs(event_close - swing_price) / swing_price
        disp_pct = disp * 100
        if disp_pct >= 0.20:
            score += 15
            breakdown["displacement"] = 15
        elif disp_pct >= 0.10:
            score += 10
            breakdown["displacement"] = 10
        elif disp_pct >= 0.05:
            score += 5
            breakdown["displacement"] = 5
        else:
            breakdown["displacement"] = 0

        # ── C5: External / Internal structure (+15 / +5) ──
        is_external = False
        # External: breaking a swing at/near the overall range extreme
        if event["direction"] == "bullish" and top_high and swing_price >= top_high * 0.995:
            is_external = True
        elif event["direction"] == "bearish" and bottom_low and swing_price <= bottom_low * 1.005:
            is_external = True

        # Also: if it breaks the most recent major swing
        if not is_external:
            if event["direction"] == "bullish":
                recent_highs = [s for s in classified if s["type"] in ("HH", "LH")]
                if recent_highs and swing_price >= recent_highs[-1]["price"] * 0.998:
                    is_external = True
            else:
                recent_lows = [s for s in classified if s["type"] in ("HL", "LL")]
                if recent_lows and swing_price <= recent_lows[-1]["price"] * 1.002:
                    is_external = True

        if is_external:
            score += 15
            event["bos_type"] = "External"
            breakdown["structure"] = 15
        else:
            score += 5
            event["bos_type"] = "Internal"
            breakdown["structure"] = 5

        # ── C6: ATR expansion (+10) ──
        candle_range = break_candle["high"] - break_candle["low"]
        if atr > 0 and candle_range >= atr * 1.2:
            score += 10
            breakdown["atr_expansion"] = 10
        elif atr > 0 and candle_range >= atr * 0.8:
            score += 5
            breakdown["atr_expansion"] = 5
        else:
            breakdown["atr_expansion"] = 0

        # ── C7: Distance from previous BOS (+5) ──
        dist = event["candle_index"] - prev_break_idx
        if dist >= 20:
            score += 5
            breakdown["bos_distance"] = 5
        elif dist >= 10:
            score += 3
            breakdown["bos_distance"] = 3
        else:
            breakdown["bos_distance"] = 0

        # ── C8: Volume confirmation (+5) ──
        if avg_volume > 0:
            # Volume increase on break candle compared to pre-break average
            # Use 3 candles before the break as baseline
            vol_baseline_candles = []
            for c in candles:
                if 0 <= event["candle_index"] - c["index"] <= 3 and c["index"] < event["candle_index"]:
                    vol_baseline_candles.append(c["volume"])
            if vol_baseline_candles:
                vol_baseline = sum(vol_baseline_candles) / len(vol_baseline_candles)
                if break_candle["volume"] >= vol_baseline * 1.3:
                    score += 5
                    breakdown["volume"] = 5
                elif break_candle["volume"] >= vol_baseline * 1.1:
                    score += 2
                    breakdown["volume"] = 2
                else:
                    breakdown["volume"] = 0
            else:
                breakdown["volume"] = 0
        else:
            breakdown["volume"] = 0

        event["score"] = min(score, 100)
        event["breakdown"] = breakdown

        if score >= 80:
            event["classification"] = "Strong BOS"
        elif score >= 60:
            event["classification"] = "Good BOS"
        elif score >= 40:
            event["classification"] = "Weak BOS"
        else:
            event["classification"] = "Ignore"

        prev_break_idx = event["candle_index"]

    return sorted_bos
