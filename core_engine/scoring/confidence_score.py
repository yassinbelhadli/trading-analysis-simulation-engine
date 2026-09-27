# confidence_score.py
import pandas as pd
import numpy as np


class ConfidenceScoreEngine:
    def __init__(
        self,
        min_confidence=50,
        premium_confidence=68,
        elite_confidence=82,
        max_confidence=98
    ):
        self.min_confidence = min_confidence
        self.premium_confidence = premium_confidence
        self.elite_confidence = elite_confidence
        self.max_confidence = max_confidence

    def _safe_bool(self, row, col):
        try:
            return bool(row.get(col, False))
        except Exception:
            return False

    def _safe_str(self, row, col, default=""):
        try:
            val = row.get(col, default)
            if pd.isna(val) or val is None:
                return default
            return str(val)
        except Exception:
            return default

    def _safe_float(self, row, col, default=0.0):
        try:
            value = row.get(col, default)
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default

    def _has_active_zone(self, row, direction):
        if direction == "BUY":
            return (
                self._safe_str(row, "Active_OB_Type") == "Bullish"
                or self._safe_str(row, "Active_FVG_Type") == "Bullish"
                or self._safe_bool(row, "Bullish_OB")
                or self._safe_bool(row, "Bullish_FVG")
            )

        if direction == "SELL":
            return (
                self._safe_str(row, "Active_OB_Type") == "Bearish"
                or self._safe_str(row, "Active_FVG_Type") == "Bearish"
                or self._safe_bool(row, "Bearish_OB")
                or self._safe_bool(row, "Bearish_FVG")
            )

        return False

    def _direction_alignment(self, row, direction):
        score = 0

        if direction == "BUY":
            if self._safe_str(row, "PD_State") in ["DISCOUNT", "EQUILIBRIUM"] or self._safe_bool(row, "PD_Valid_Buy"):
                score += 10
            if self._safe_bool(row, "SR_Valid_Buy") or self._safe_bool(row, "Near_Support"):
                score += 7
            if self._safe_bool(row, "Candle_Valid_Buy") or self._safe_str(row, "Candle_Direction") == "Bullish":
                score += 8
            if self._safe_str(row, "Active_FVG_Type") == "Bullish" or self._safe_bool(row, "Bullish_FVG"):
                score += 6
            if self._safe_str(row, "Active_OB_Type") == "Bullish" or self._safe_bool(row, "Bullish_OB"):
                score += 6
            if self._safe_bool(row, "Bullish_VI"):
                score += 3
            if self._safe_bool(row, "Bullish_LV"):
                score += 4

        elif direction == "SELL":
            if self._safe_str(row, "PD_State") in ["PREMIUM", "EQUILIBRIUM"] or self._safe_bool(row, "PD_Valid_Sell"):
                score += 10
            if self._safe_bool(row, "SR_Valid_Sell") or self._safe_bool(row, "Near_Resistance"):
                score += 7
            if self._safe_bool(row, "Candle_Valid_Sell") or self._safe_str(row, "Candle_Direction") == "Bearish":
                score += 8
            if self._safe_str(row, "Active_FVG_Type") == "Bearish" or self._safe_bool(row, "Bearish_FVG"):
                score += 6
            if self._safe_str(row, "Active_OB_Type") == "Bearish" or self._safe_bool(row, "Bearish_OB"):
                score += 6
            if self._safe_bool(row, "Bearish_VI"):
                score += 3
            if self._safe_bool(row, "Bearish_LV"):
                score += 4

        return min(score, 40)

    def _structure_confidence(self, row, direction):
        score = 0

        if self._safe_bool(row, "MSS"):
            score += 24
        elif self._safe_bool(row, "CHoCH"):
            score += 18
        elif self._safe_bool(row, "BOS"):
            score += 14

        trend = str(row.get("Market_Trend", ""))

        if direction == "BUY" and "BULLISH" in trend:
            score += 10

        if direction == "SELL" and "BEARISH" in trend:
            score += 10

        return min(score, 35)

    def _liquidity_confidence(self, row):
        score = 0

        if self._safe_bool(row, "Valid_Sweep"):
            score += 18
        elif self._safe_bool(row, "Liquidity_Sweep"):
            score += 10

        liquidity_rank = self._safe_float(row, "Liquidity_Rank", 0)
        score += min(liquidity_rank, 12)

        sweep_strength = self._safe_float(row, "Sweep_Strength", 0)
        if sweep_strength >= 5:
            score += 6
        elif sweep_strength >= 2:
            score += 4
        elif sweep_strength > 0:
            score += 2

        return min(score, 35)

    def _imbalance_confidence(self, row, direction):
        score = 0

        if direction == "BUY":
            if self._safe_str(row, "Active_FVG_Type") == "Bullish" or self._safe_bool(row, "Bullish_FVG"):
                score += 10
            if self._safe_str(row, "Active_OB_Type") == "Bullish" or self._safe_bool(row, "Bullish_OB"):
                score += 10
            if self._safe_bool(row, "Bullish_VI"):
                score += 4
            if self._safe_bool(row, "Bullish_LV"):
                score += 5

        elif direction == "SELL":
            if self._safe_str(row, "Active_FVG_Type") == "Bearish" or self._safe_bool(row, "Bearish_FVG"):
                score += 10
            if self._safe_str(row, "Active_OB_Type") == "Bearish" or self._safe_bool(row, "Bearish_OB"):
                score += 10
            if self._safe_bool(row, "Bearish_VI"):
                score += 4
            if self._safe_bool(row, "Bearish_LV"):
                score += 5

        return min(score, 30)

    def _penalties(self, row, direction):
        penalty = 0
        reasons = []

        if not self._safe_bool(row, "Setup_Approved"):
            penalty += 8
            reasons.append("SETUP_NOT_APPROVED_SOFT")

        if direction == "BUY" and self._safe_str(row, "PD_State") == "PREMIUM":
            penalty += 6
            reasons.append("BUY_IN_PREMIUM")

        if direction == "SELL" and self._safe_str(row, "PD_State") == "DISCOUNT":
            penalty += 6
            reasons.append("SELL_IN_DISCOUNT")

        if self._safe_str(row, "Setup_Session") == "OTHER":
            penalty += 5
            reasons.append("BAD_SESSION")

        reject_reason = row.get("Setup_Reject_Reason")
        if reject_reason not in [None, "APPROVED"]:
            penalty += 4
            reasons.append(str(reject_reason))

        return penalty, reasons

    def _label_confidence(self, confidence):
        if confidence >= self.elite_confidence:
            return "ELITE"
        if confidence >= self.premium_confidence:
            return "PREMIUM"
        if confidence >= self.min_confidence:
            return "STANDARD"
        if confidence >= 42:
            return "LOW"
        return "NO_TRADE"

    def process_confidence(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df["Confidence_Score"] = 0.0
        df["Confidence_Label"] = "NO_TRADE"
        df["Confidence_Approved"] = False
        df["Confidence_Reason"] = None

        df["Structure_Confidence"] = 0.0
        df["Liquidity_Confidence"] = 0.0
        df["Imbalance_Confidence"] = 0.0
        df["Direction_Alignment"] = 0.0
        df["Confidence_Penalty"] = 0.0

        for i in range(len(df)):
            row = df.iloc[i]
            direction = row.get("Trade_Direction", None)

            if direction not in ["BUY", "SELL"]:
                df.at[df.index[i], "Confidence_Reason"] = "NO_DIRECTION"
                continue

            base_score = self._safe_float(
                row,
                "Setup_Final_Score",
                self._safe_float(row, "Setup_Score", 0)
            )

            structure_score = self._structure_confidence(row, direction)
            liquidity_score = self._liquidity_confidence(row)
            imbalance_score = self._imbalance_confidence(row, direction)
            alignment_score = self._direction_alignment(row, direction)

            raw_confidence = (
                base_score * 0.50
                + structure_score * 0.15
                + liquidity_score * 0.10
                + imbalance_score * 0.15
                + alignment_score * 0.10
            )

            if self._has_active_zone(row, direction):
                raw_confidence += 8

            if self._safe_bool(row, "Setup_Approved"):
                raw_confidence += 5

            penalty, penalty_reasons = self._penalties(row, direction)

            confidence = raw_confidence - penalty
            confidence = max(0, min(confidence, self.max_confidence))

            label = self._label_confidence(confidence)

            approved = (
                confidence >= self.min_confidence
                and label in ["STANDARD", "PREMIUM", "ELITE"]
                and self._has_active_zone(row, direction)
            )

            df.at[df.index[i], "Structure_Confidence"] = structure_score
            df.at[df.index[i], "Liquidity_Confidence"] = liquidity_score
            df.at[df.index[i], "Imbalance_Confidence"] = imbalance_score
            df.at[df.index[i], "Direction_Alignment"] = alignment_score
            df.at[df.index[i], "Confidence_Penalty"] = penalty

            df.at[df.index[i], "Confidence_Score"] = round(confidence, 2)
            df.at[df.index[i], "Confidence_Label"] = label
            df.at[df.index[i], "Confidence_Approved"] = approved
            df.at[df.index[i], "Confidence_Reason"] = "+".join(penalty_reasons) if penalty_reasons else "CLEAN"

        return df

    def get_tradeable_setups(self, df: pd.DataFrame):
        if "Confidence_Approved" not in df.columns:
            return pd.DataFrame()
        return df[df["Confidence_Approved"] == True].copy()

    def get_confidence_summary(self, df: pd.DataFrame):
        if "Confidence_Label" not in df.columns:
            return {}

        return {
            "total_rows": len(df),
            "tradeable_setups": int(df["Confidence_Approved"].sum()),
            "avg_confidence": round(df["Confidence_Score"].mean(), 2),
            "max_confidence": round(df["Confidence_Score"].max(), 2),
            "labels": df["Confidence_Label"].value_counts(dropna=False).to_dict(),
        }