# trade_quality_filter.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import pandas as pd


@dataclass
class TradeQualityResult:
    allowed: bool
    state: str
    reason: str
    score: float
    required_score: float
    sl_distance: float
    max_sl_distance: float
    raw_lot_size: float
    active_ob_type: Optional[str]
    active_fvg_type: Optional[str]
    entry_source: Optional[str]
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TradeQualityFilter:
    def __init__(
        self,
        min_setup_score: float = 65.0,
        sell_fvg_min_score: float = 68.0,
        sell_ob_min_score: float = 72.0,
        buy_fvg_min_score: float = 65.0,
        buy_ob_min_score: float = 65.0,
        max_sl_distance_gold: float = 45.0,
        max_sl_distance_nasdaq: float = 180.0,
        max_sl_distance_btc: float = 1200.0,
        reject_raw_lot_below_min: bool = True,
        min_raw_lot_size: float = 0.01,
        reject_strong_zone_conflict: bool = False,
    ):
        self.min_setup_score = min_setup_score
        self.sell_fvg_min_score = sell_fvg_min_score
        self.sell_ob_min_score = sell_ob_min_score
        self.buy_fvg_min_score = buy_fvg_min_score
        self.buy_ob_min_score = buy_ob_min_score
        self.max_sl_distance_gold = max_sl_distance_gold
        self.max_sl_distance_nasdaq = max_sl_distance_nasdaq
        self.max_sl_distance_btc = max_sl_distance_btc
        self.reject_raw_lot_below_min = reject_raw_lot_below_min
        self.min_raw_lot_size = min_raw_lot_size
        self.reject_strong_zone_conflict = reject_strong_zone_conflict

    def evaluate(
        self,
        row: pd.Series,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        entry_source: str,
        lot_result: Any,
    ) -> TradeQualityResult:

        setup_score = self._safe_float(row.get("Setup_Score", row.get("Setup_Final_Score", 0)))
        required_score = self._required_score(direction, entry_source)

        sl_distance = abs(float(entry_price) - float(stop_loss))

        normalized_symbol = str(symbol).upper()
        max_sl_distance = self._get_max_sl_distance(normalized_symbol)

        raw_lot_size = self._extract_raw_lot(lot_result)

        active_ob_type = row.get("Active_OB_Type", None)
        active_fvg_type = row.get("Active_FVG_Type", None)

        if setup_score < required_score:
            return self._reject(
                "LOW_DYNAMIC_SETUP_SCORE",
                setup_score,
                required_score,
                sl_distance,
                max_sl_distance,
                raw_lot_size,
                active_ob_type,
                active_fvg_type,
                entry_source,
                f"Setup score {setup_score:.2f} below required {required_score:.2f}",
            )

        if sl_distance > max_sl_distance:
            return self._reject(
                "SL_TOO_WIDE",
                setup_score,
                required_score,
                sl_distance,
                max_sl_distance,
                raw_lot_size,
                active_ob_type,
                active_fvg_type,
                entry_source,
                f"SL distance {sl_distance:.2f} above max {max_sl_distance:.2f}",
            )

        if self.reject_raw_lot_below_min and raw_lot_size < self.min_raw_lot_size:
            return self._reject(
                "RAW_LOT_BELOW_MIN_LOT",
                setup_score,
                required_score,
                sl_distance,
                max_sl_distance,
                raw_lot_size,
                active_ob_type,
                active_fvg_type,
                entry_source,
                f"Raw lot {raw_lot_size:.4f} below {self.min_raw_lot_size:.2f}",
            )

        if self.reject_strong_zone_conflict:
            if self._has_strong_conflict(direction, active_ob_type, active_fvg_type, entry_source):
                return self._reject(
                    "ZONE_CONFLICT_STRONG",
                    setup_score,
                    required_score,
                    sl_distance,
                    max_sl_distance,
                    raw_lot_size,
                    active_ob_type,
                    active_fvg_type,
                    entry_source,
                    "Active OB/FVG conflict against selected entry source",
                )

        return TradeQualityResult(
            allowed=True,
            state="SAFE",
            reason="OK",
            score=round(setup_score, 2),
            required_score=round(required_score, 2),
            sl_distance=round(sl_distance, 5),
            max_sl_distance=max_sl_distance,
            raw_lot_size=round(raw_lot_size, 5),
            active_ob_type=active_ob_type,
            active_fvg_type=active_fvg_type,
            entry_source=entry_source,
            warning=None,
        )

    def _get_max_sl_distance(self, normalized_symbol: str) -> float:
        s = str(normalized_symbol).upper()

        if "XAU" in s or "GOLD" in s:
            return self.max_sl_distance_gold

        if "BTC" in s or "XBT" in s or "BITCOIN" in s:
            return self.max_sl_distance_btc

        return self.max_sl_distance_nasdaq

    def _required_score(self, direction: str, entry_source: str) -> float:
        src = str(entry_source or "").upper()

        if direction == "SELL" and "OB" in src:
            return self.sell_ob_min_score

        if direction == "SELL" and "FVG" in src:
            return self.sell_fvg_min_score

        if direction == "BUY" and "OB" in src:
            return self.buy_ob_min_score

        if direction == "BUY" and "FVG" in src:
            return self.buy_fvg_min_score

        return self.min_setup_score

    def _has_strong_conflict(self, direction, active_ob_type, active_fvg_type, entry_source) -> bool:
        if direction == "BUY":
            if "OB" in entry_source and active_fvg_type == "Bearish":
                return True
            if "FVG" in entry_source and active_ob_type == "Bearish":
                return True

        if direction == "SELL":
            if "OB" in entry_source and active_fvg_type == "Bullish":
                return True
            if "FVG" in entry_source and active_ob_type == "Bullish":
                return True

        return False

    def _extract_raw_lot(self, lot_result: Any) -> float:
        if lot_result is None:
            return 0.0

        if hasattr(lot_result, "raw_lot_size"):
            return self._safe_float(getattr(lot_result, "raw_lot_size", 0.0))

        if isinstance(lot_result, dict):
            return self._safe_float(lot_result.get("raw_lot_size", 0.0))

        return 0.0

    def _reject(
        self,
        reason,
        score,
        required_score,
        sl_distance,
        max_sl_distance,
        raw_lot_size,
        active_ob_type,
        active_fvg_type,
        entry_source,
        warning,
    ) -> TradeQualityResult:
        return TradeQualityResult(
            allowed=False,
            state="BLOCKED",
            reason=reason,
            score=round(score, 2),
            required_score=round(required_score, 2),
            sl_distance=round(sl_distance, 5),
            max_sl_distance=max_sl_distance,
            raw_lot_size=round(raw_lot_size, 5),
            active_ob_type=active_ob_type,
            active_fvg_type=active_fvg_type,
            entry_source=entry_source,
            warning=warning,
        )

    def _safe_float(self, value, default=0.0) -> float:
        try:
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default