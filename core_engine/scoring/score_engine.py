# score_engine.py
import pandas as pd
import numpy as np

from core_engine.scoring.score_breakdown import ScoreBreakdown


class ScoreEngine:
    def __init__(self):
        self.weights = {
            "MSS": 25,
            "CHOCH": 20,
            "BOS": 15,
            "VALID_SWEEP": 20,
            "SWEEP_STRENGTH": 10,
            "FVG": 10,
            "OB": 15,
            "VI": 8,
            "LV": 8,
            "DISCOUNT_PREMIUM": 10,
            "SR": 10,
            "CANDLE": 10,
            "DIRECTION_CONTEXT": 5,
        }

    def process_score(self, df: pd.DataFrame, structure_lookback: int = 50):
        df = df.copy()

        # Forward-fill structure events so subsequent bars inherit them
        for col in ("BOS", "CHoCH", "MSS"):
            if col in df.columns:
                df[col] = df[col].replace(False, pd.NA).ffill().fillna(False).astype(bool)

        # Also forward-fill type columns for direction inference
        for col in ("BOS_Type", "CHoCH_Type", "MSS_Type", "Sweep_Type", "Active_OB_Type", "Active_FVG_Type", "OB_Context", "Active_OB_Context"):
            if col in df.columns:
                df[col] = df[col].replace([None, ""], pd.NA).ffill()

        df["Setup_Score"] = 0.0
        df["Trade_Direction"] = None
        df["Setup_Quality"] = None
        df["Direction_Source"] = None

        for i in range(len(df)):
            row = df.iloc[i]

            score = 0.0

            breakdown = ScoreBreakdown(
    reasons={}
)
            direction, direction_source = self._infer_direction(row)

            # Structure
            if self._is_true(row, "MSS"):
                score += self.weights["MSS"]
                breakdown.structure += self.weights["MSS"]
                breakdown.reasons["MSS"] = self.weights["MSS"]

            if self._is_true(row, "CHoCH"):
                score += self.weights["CHOCH"]
                breakdown.structure += self.weights["CHOCH"]
                breakdown.reasons["CHoCH"] = self.weights["CHOCH"]

            if self._is_true(row, "BOS"):
                score += self.weights["BOS"]
                breakdown.structure += self.weights["BOS"]
                breakdown.reasons["BOS"] = self.weights["BOS"]

            # Liquidity
            if self._is_true(row, "Valid_Sweep"):
                score += self.weights["VALID_SWEEP"]
                breakdown.liquidity += self.weights["VALID_SWEEP"]
                breakdown.reasons["Liquidity Sweep"] = self.weights["VALID_SWEEP"]

            sweep_strength = self._safe_float(row.get("Sweep_Strength", 0))
            if sweep_strength > 0:
                score += min(sweep_strength, self.weights["SWEEP_STRENGTH"])

            # Directional FVG
            if direction == "BUY":
                if self._is_true(row, "Bullish_FVG") or (self._is_true(row, "Active_FVG_Valid") and self._safe_eq(row.get("Active_FVG_Type"), "Bullish")):
                    score += self.weights["FVG"]
            elif direction == "SELL":
                if self._is_true(row, "Bearish_FVG") or (self._is_true(row, "Active_FVG_Valid") and self._safe_eq(row.get("Active_FVG_Type"), "Bearish")):
                    score += self.weights["FVG"]
            else:
                if self._is_true(row, "FVG_Valid"):
                    score += self.weights["FVG"]

            # Directional OB
            if direction == "BUY":
                if self._is_true(row, "Bullish_OB") or (self._is_true(row, "Active_OB_Valid") and self._safe_eq(row.get("Active_OB_Type"), "Bullish")):
                    score += self.weights["OB"]
            elif direction == "SELL":
                if self._is_true(row, "Bearish_OB") or (self._is_true(row, "Active_OB_Valid") and self._safe_eq(row.get("Active_OB_Type"), "Bearish")):
                    score += self.weights["OB"]
            else:
                if self._is_true(row, "OB_Valid"):
                    score += self.weights["OB"]

            # VI
            if direction == "BUY":
                if self._is_true(row, "Bullish_VI") or self._is_true(row, "VI_Valid"):
                    score += self.weights["VI"]
            elif direction == "SELL":
                if self._is_true(row, "Bearish_VI") or self._is_true(row, "VI_Valid"):
                    score += self.weights["VI"]
            else:
                if self._is_true(row, "VI_Valid"):
                    score += self.weights["VI"]

            # LV
            if direction == "BUY":
                if self._is_true(row, "Bullish_LV") or self._is_true(row, "LV_Valid"):
                    score += self.weights["LV"]
            elif direction == "SELL":
                if self._is_true(row, "Bearish_LV") or self._is_true(row, "LV_Valid"):
                    score += self.weights["LV"]
            else:
                if self._is_true(row, "LV_Valid"):
                    score += self.weights["LV"]

            # Premium / Discount
            if direction == "BUY":
                if self._is_true(row, "Discount_Zone") or self._is_true(row, "PD_Valid_Buy") or self._safe_str(row.get("PD_State")) == "DISCOUNT":
                    score += self.weights["DISCOUNT_PREMIUM"]

            elif direction == "SELL":
                if self._is_true(row, "Premium_Zone") or self._is_true(row, "PD_Valid_Sell") or self._safe_str(row.get("PD_State")) == "PREMIUM":
                    score += self.weights["DISCOUNT_PREMIUM"]

            # Support / Resistance
            if direction == "BUY":
                if self._is_true(row, "SR_Valid_Buy") or self._is_true(row, "Near_Support"):
                    score += self.weights["SR"]

            elif direction == "SELL":
                if self._is_true(row, "SR_Valid_Sell") or self._is_true(row, "Near_Resistance"):
                    score += self.weights["SR"]

            # Candle confirmation
            if self._candle_ok(row, direction):
                score += self.weights["CANDLE"]

            if direction is not None:
                score += self.weights["DIRECTION_CONTEXT"]

            score = min(score, 100)

            df.at[df.index[i], "Setup_Score"] = round(score, 5)
            df.at[df.index[i], "Trade_Direction"] = direction
            df.at[df.index[i], "Direction_Source"] = direction_source
            df.at[df.index[i], "Setup_Quality"] = self._quality(score)

        return df

    def _safe_str(self, val) -> str:
        try:
            if pd.isna(val) or val is None:
                return ""
            return str(val)
        except Exception:
            return ""

    def _safe_eq(self, val, target: str) -> bool:
        try:
            if pd.isna(val) or val is None:
                return False
            return str(val) == target
        except Exception:
            return False

    def _infer_direction(self, row):
        mss_type = self._safe_str(row.get("MSS_Type"))
        bos_type = self._safe_str(row.get("BOS_Type"))
        choch_type = self._safe_str(row.get("CHoCH_Type"))

        if self._is_true(row, "MSS"):
            if "Bullish" in mss_type or "BULLISH" in mss_type:
                return "BUY", "MSS_BULLISH"
            if "Bearish" in mss_type or "BEARISH" in mss_type:
                return "SELL", "MSS_BEARISH"

        if self._is_true(row, "CHoCH"):
            if "Bullish" in choch_type or "BULLISH" in choch_type:
                return "BUY", "CHOCH_BULLISH"
            if "Bearish" in choch_type or "BEARISH" in choch_type:
                return "SELL", "CHOCH_BEARISH"

        if self._is_true(row, "BOS"):
            if "Bullish" in bos_type or "BULLISH" in bos_type:
                return "BUY", "BOS_BULLISH"
            if "Bearish" in bos_type or "BEARISH" in bos_type:
                return "SELL", "BOS_BEARISH"

        if self._is_true(row, "Valid_Sweep") or self._is_true(row, "Liquidity_Sweep"):
            sweep_type = self._safe_str(row.get("Sweep_Type", row.get("Liquidity_Sweep_Type", "")))
            if "LOW" in sweep_type.upper() or "SELLSIDE" in sweep_type.upper() or "BEARISH_LIQUIDITY_TAKEN" in sweep_type.upper():
                return "BUY", "SWEEP_LOW_REVERSAL"
            if "HIGH" in sweep_type.upper() or "BUYSIDE" in sweep_type.upper() or "BULLISH_LIQUIDITY_TAKEN" in sweep_type.upper():
                return "SELL", "SWEEP_HIGH_REVERSAL"

        if self._is_true(row, "PD_Valid_Buy") or self._safe_str(row.get("PD_State")) == "DISCOUNT":
            if self._is_true(row, "Bullish_FVG") or self._is_true(row, "Bullish_OB") or self._safe_eq(row.get("Active_OB_Type"), "Bullish") or self._safe_eq(row.get("Active_FVG_Type"), "Bullish"):
                return "BUY", "PD_BUY_ZONE"

        if self._is_true(row, "PD_Valid_Sell") or self._safe_str(row.get("PD_State")) == "PREMIUM":
            if self._is_true(row, "Bearish_FVG") or self._is_true(row, "Bearish_OB") or self._safe_eq(row.get("Active_OB_Type"), "Bearish") or self._safe_eq(row.get("Active_FVG_Type"), "Bearish"):
                return "SELL", "PD_SELL_ZONE"

        if self._safe_eq(row.get("Active_OB_Type"), "Bullish") and (
            self._is_true(row, "SR_Valid_Buy") or self._is_true(row, "Candle_Valid_Buy") or self._safe_str(row.get("Candle_Direction")) == "Bullish"
        ):
            return "BUY", "ACTIVE_OB_BULLISH_CONTEXT"

        if self._safe_eq(row.get("Active_OB_Type"), "Bearish") and (
            self._is_true(row, "SR_Valid_Sell") or self._is_true(row, "Candle_Valid_Sell") or self._safe_str(row.get("Candle_Direction")) == "Bearish"
        ):
            return "SELL", "ACTIVE_OB_BEARISH_CONTEXT"

        if self._safe_eq(row.get("Active_FVG_Type"), "Bullish") and (
            self._is_true(row, "SR_Valid_Buy") or self._is_true(row, "Candle_Valid_Buy") or self._safe_str(row.get("Candle_Direction")) == "Bullish"
        ):
            return "BUY", "ACTIVE_FVG_BULLISH_CONTEXT"

        if self._safe_eq(row.get("Active_FVG_Type"), "Bearish") and (
            self._is_true(row, "SR_Valid_Sell") or self._is_true(row, "Candle_Valid_Sell") or self._safe_str(row.get("Candle_Direction")) == "Bearish"
        ):
            return "SELL", "ACTIVE_FVG_BEARISH_CONTEXT"

        return None, "NO_DIRECTION"

    def _candle_ok(self, row, direction):
        if direction == "BUY":
            return (
                self._is_true(row, "Candle_Valid_Buy")
                or self._safe_str(row.get("Candle_Direction")) == "Bullish"
                or self._is_true(row, "Bullish_Engulfing")
                or self._is_true(row, "Hammer")
                or self._is_true(row, "Morning_Star")
            )

        if direction == "SELL":
            return (
                self._is_true(row, "Candle_Valid_Sell")
                or self._safe_str(row.get("Candle_Direction")) == "Bearish"
                or self._is_true(row, "Bearish_Engulfing")
                or self._is_true(row, "Shooting_Star")
                or self._is_true(row, "Evening_Star")
            )

        return False

    def _quality(self, score):
        if score >= 85:
            return "A+"
        if score >= 75:
            return "A"
        if score >= 65:
            return "B"
        if score >= 50:
            return "C"
        return "IGNORE"

    def _is_true(self, row, col):
        try:
            return bool(row.get(col, False))
        except Exception:
            return False

    def _safe_float(self, value, default=0.0):
        try:
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default