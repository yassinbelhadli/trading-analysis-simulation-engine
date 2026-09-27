"""ICT Structure State Machine — sequential stateful CHoCH / MSS detection.

Tracks market structure states candle-by-candle:

  States:
    INIT            — not enough data
    BULLISH_TREND   — forming HH/HL (higher highs, higher lows)
    BEARISH_TREND   — forming LH/LL (lower highs, lower lows)
    RANGING         — no clear direction

  Events emitted:
    BOS           — same-trend swing break
    CHoCH         — trend reversal detected (state transition)
    MSS           — CHoCH + confirmed swing in new direction
"""

import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _classify_swing_pair(high1: float, low1: float,
                          high2: float, low2: float) -> str:
    """Classify the relationship between two swing points.

    Returns: 'bullish', 'bearish', or 'ranging'
    """
    higher_high = high2 > high1 * 1.0001
    higher_low = low2 > low1 * 1.0001
    lower_high = high2 < high1 * 0.9999
    lower_low = low2 < low1 * 0.9999

    if higher_high and higher_low:
        return "bullish"
    elif lower_high and lower_low:
        return "bearish"
    else:
        return "ranging"


class StructureStateMachine:
    """Sequential state machine for ICT market structure."""

    def __init__(self):
        self.state = "INIT"
        self.swings: List[Dict] = []
        self.highs: List[Dict] = []   # HH/LH candidates
        self.lows: List[Dict] = []    # HL/LL candidates
        self.bos_events: List[Dict] = []
        self.choch_events: List[Dict] = []
        self.mss_events: List[Dict] = []
        self.last_high_price: Optional[float] = None
        self.last_low_price: Optional[float] = None
        self.last_high_idx: Optional[int] = None
        self.last_low_idx: Optional[int] = None
        self.pending_choch: Optional[Dict] = None
        self.confirmed_high_idx: Optional[int] = None
        self.confirmed_low_idx: Optional[int] = None
        self._broken_highs: set = set()
        self._broken_lows: set = set()
        self._last_choch_idx: Optional[int] = None
        self._last_choch_price: Optional[float] = None

    def _update_trend_state(self, new_high: float, new_low: float):
        """Update trend state based on new swing pair."""
        if len(self.highs) < 2 or len(self.lows) < 2:
            self.state = "RANGING"
            return

        # Compare last two completed swing pairs
        h1 = self.highs[-2]["price"]
        h2 = self.highs[-1]["price"]
        l1 = self.lows[-2]["price"]
        l2 = self.lows[-1]["price"]

        trend = _classify_swing_pair(h1, l1, h2, l2)

        if trend == "bullish":
            self.state = "BULLISH_TREND"
        elif trend == "bearish":
            self.state = "BEARISH_TREND"
        else:
            self.state = "RANGING"

    def _check_bos(self, candle: Dict, current_highs: List[Dict],
                   current_lows: List[Dict]) -> Optional[Dict]:
        """Check for Break of Structure on this candle."""
        # Bullish BOS: close above the most recent swing high
        if current_highs and candle["close"] > self.last_high_price * 1.0003:
            return {
                "candle_index": candle["index"],
                "price": self.last_high_price,
                "direction": "bullish",
                "swing_index": self.last_high_idx,
                "swing_type": current_highs[-1]["type"],
                "displacement_pct": round(
                    (candle["close"] - self.last_high_price) / self.last_high_price * 100, 3),
            }

        # Bearish BOS: close below the most recent swing low
        if current_lows and candle["close"] < self.last_low_price * 0.9997:
            return {
                "candle_index": candle["index"],
                "price": self.last_low_price,
                "direction": "bearish",
                "swing_index": self.last_low_idx,
                "swing_type": current_lows[-1]["type"],
                "displacement_pct": round(
                    (self.last_low_price - candle["close"]) / self.last_low_price * 100, 3),
            }

        return None

    def _check_choch(self, candle: Dict, current_highs: List[Dict],
                     current_lows: List[Dict]) -> Optional[Dict]:
        """Check for Change of Character (trend reversal)."""
        if self.state == "BEARISH_TREND" and current_highs:
            # In bearish structure: CHoCH to bullish = close above last LH
            last_h = current_highs[-1]
            if candle["close"] > last_h["price"] * 1.0003:
                return {
                    "candle_index": candle["index"],
                    "price": last_h["price"],
                    "direction": "bullish",
                    "swing_index": last_h["index"],
                    "displacement_pct": round(
                        (candle["close"] - last_h["price"]) / last_h["price"] * 100, 3),
                }

        elif self.state == "BULLISH_TREND" and current_lows:
            # In bullish structure: CHoCH to bearish = close below last HL
            last_l = current_lows[-1]
            if candle["close"] < last_l["price"] * 0.9997:
                return {
                    "candle_index": candle["index"],
                    "price": last_l["price"],
                    "direction": "bearish",
                    "swing_index": last_l["index"],
                    "displacement_pct": round(
                        (last_l["price"] - candle["close"]) / last_l["price"] * 100, 3),
                }

        return None

    def _check_mss_confirmation(self, candle: Dict, current_highs: List[Dict],
                                 current_lows: List[Dict]) -> Optional[Dict]:
        """Check if a pending CHoCH is confirmed by a swing in new direction."""
        if not self.pending_choch:
            return None

        choch = self.pending_choch
        if choch["direction"] == "bullish":
            # Confirm: new low (HL) forms above the CHoCH low
            if current_lows and current_lows[-1]["index"] > choch["candle_index"]:
                # New low formed after CHoCH
                if self.confirmed_low_idx is not None and \
                   current_lows[-1]["index"] > self.confirmed_low_idx:
                    return None  # already confirmed
                # The new low must be higher than the last bearish low to confirm
                if len(current_lows) >= 2:
                    prev_low = current_lows[-2]
                    if current_lows[-1]["price"] > prev_low["price"]:
                        choch["mss_confirmed"] = True
                        choch["confirm_candle"] = candle["index"]
                        choch["confirm_price"] = current_lows[-1]["price"]
                        self.confirmed_low_idx = current_lows[-1]["index"]
                        self.pending_choch = None
                        return dict(choch)

        else:
            # Confirm: new high (LH) forms below the CHoCH high
            if current_highs and current_highs[-1]["index"] > choch["candle_index"]:
                if self.confirmed_high_idx is not None and \
                   current_highs[-1]["index"] > self.confirmed_high_idx:
                    return None
                if len(current_highs) >= 2:
                    prev_high = current_highs[-2]
                    if current_highs[-1]["price"] < prev_high["price"]:
                        choch["mss_confirmed"] = True
                        choch["confirm_candle"] = candle["index"]
                        choch["confirm_price"] = current_highs[-1]["price"]
                        self.confirmed_high_idx = current_highs[-1]["index"]
                        self.pending_choch = None
                        return dict(choch)

        return None

    def feed_candle(self, candle: Dict, swings: List[Dict]):
        """Process one candle through the state machine."""
        idx = candle["index"]

        # Check if this candle has a new swing
        new_swings = [s for s in swings if s["index"] == idx and
                      s["type"] in ("swing_high", "swing_low")]

        for s in new_swings:
            if s["type"] == "swing_high":
                if self.last_high_price is None:
                    s["type"] = "HH"
                elif s["price"] > self.last_high_price * 1.0001:
                    s["type"] = "HH"
                else:
                    s["type"] = "LH"
                self.highs.append(s)
                self.last_high_price = s["price"]
                self.last_high_idx = s["index"]
                self._update_trend_state(s["price"], self.lows[-1]["price"] if self.lows else s["price"])

            elif s["type"] == "swing_low":
                if self.last_low_price is None:
                    s["type"] = "LL"
                elif s["price"] < self.last_low_price * 0.9999:
                    s["type"] = "LL"
                else:
                    s["type"] = "HL"
                self.lows.append(s)
                self.last_low_price = s["price"]
                self.last_low_idx = s["index"]
                self._update_trend_state(self.highs[-1]["price"] if self.highs else s["price"], s["price"])

        # Build view of current classified swings
        current_highs = [{"index": h["index"], "price": h["price"],
                          "type": h.get("classified_type", h["type"])}
                         for h in self.highs]
        current_lows = [{"index": l["index"], "price": l["price"],
                         "type": l.get("classified_type", l["type"])}
                        for l in self.lows]

        # ── BOS: only emit once per swing level ──
        if self.last_high_price is not None:
            bos_high_idx = self.last_high_idx
            if bos_high_idx not in self._broken_highs and \
               candle["close"] > self.last_high_price * 1.0003:
                self.bos_events.append({
                    "candle_index": idx, "price": self.last_high_price,
                    "direction": "bullish", "swing_index": bos_high_idx,
                    "swing_type": self.highs[-1]["type"] if self.highs else "HH",
                    "displacement_pct": round(
                        (candle["close"] - self.last_high_price) / self.last_high_price * 100, 3),
                })
                self._broken_highs.add(bos_high_idx)

        if self.last_low_price is not None:
            bos_low_idx = self.last_low_idx
            if bos_low_idx not in self._broken_lows and \
               candle["close"] < self.last_low_price * 0.9997:
                self.bos_events.append({
                    "candle_index": idx, "price": self.last_low_price,
                    "direction": "bearish", "swing_index": bos_low_idx,
                    "swing_type": self.lows[-1]["type"] if self.lows else "LL",
                    "displacement_pct": round(
                        (self.last_low_price - candle["close"]) / self.last_low_price * 100, 3),
                })
                self._broken_lows.add(bos_low_idx)

        # ── CHoCH: emit once per state transition ──
        if self.state in ("BULLISH_TREND", "BEARISH_TREND"):
            # Cooldown: skip if we already emitted CHoCH in last 3 candles
            if self._last_choch_idx is None or \
               idx - self._last_choch_idx >= 3:
                choch = self._check_choch(candle, current_highs, current_lows)
                if choch:
                    # Avoid same-price level being re-detected
                    if self._last_choch_price is None or \
                       abs(choch["price"] - self._last_choch_price) > 5:
                        choch["mss_confirmed"] = False
                        self.choch_events.append(choch)
                        self.pending_choch = choch
                        self._last_choch_idx = idx
                        self._last_choch_price = choch["price"]

        # ── MSS confirmation ──
        mss = self._check_mss_confirmation(candle, current_highs, current_lows)
        if mss:
            self.mss_events.append(mss)

    def get_results(self) -> Dict:
        """Return all detected events."""
        return {
            "bos": self.bos_events,
            "choch": self.choch_events,
            "mss": self.mss_events,
            "state_history": {
                "highs": self.highs,
                "lows": self.lows,
                "final_state": self.state,
            }
        }


def detect_structure(candles: List[Dict], swings: List[Dict]) -> Dict:
    """Run the state machine over all candles.

    Args:
        candles: full candle list (must have 'index', 'close', 'high', 'low')
        swings: all raw swings from detect_swings()

    Returns:
        dict with 'bos', 'choch', 'mss' lists + state_history
    """
    sm = StructureStateMachine()
    for c in candles:
        sm.feed_candle(c, swings)
    return sm.get_results()
