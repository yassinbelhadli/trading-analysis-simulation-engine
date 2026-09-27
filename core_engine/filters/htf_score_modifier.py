# htf_score_modifier.py
import pandas as pd


class HTFScoreModifier:
    def __init__(
        self,
        aligned_bonus=5.0,
        opposite_penalty=8.0,
        neutral_modifier=0.0,
        min_score=0.0,
        max_score=100.0,
        score_column="Setup_Score",
        output_column="Setup_Score",
    ):
        self.aligned_bonus = aligned_bonus
        self.opposite_penalty = opposite_penalty
        self.neutral_modifier = neutral_modifier
        self.min_score = min_score
        self.max_score = max_score
        self.score_column = score_column
        self.output_column = output_column

    def process_htf_score(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if self.score_column not in df.columns:
            df[self.score_column] = 0.0

        if "HTF_Bias" not in df.columns:
            df["HTF_Bias"] = "NEUTRAL"

        df["HTF_Score_Modifier"] = 0.0
        df["HTF_Score_Reason"] = "NO_DIRECTION_OR_NEUTRAL"

        for i in range(len(df)):
            direction = df["Trade_Direction"].iloc[i] if "Trade_Direction" in df.columns else None
            bias = df["HTF_Bias"].iloc[i]
            base_score = self._safe_float(df[self.score_column].iloc[i])

            modifier = self.neutral_modifier
            reason = "HTF_NEUTRAL"

            if direction == "BUY":
                if bias == "BULLISH":
                    modifier = self.aligned_bonus
                    reason = "BUY_ALIGNED_WITH_HTF_BULLISH"
                elif bias == "BEARISH":
                    modifier = -self.opposite_penalty
                    reason = "BUY_AGAINST_HTF_BEARISH"

            elif direction == "SELL":
                if bias == "BEARISH":
                    modifier = self.aligned_bonus
                    reason = "SELL_ALIGNED_WITH_HTF_BEARISH"
                elif bias == "BULLISH":
                    modifier = -self.opposite_penalty
                    reason = "SELL_AGAINST_HTF_BULLISH"

            new_score = max(
                self.min_score,
                min(self.max_score, base_score + modifier)
            )

            df.at[df.index[i], "HTF_Score_Modifier"] = modifier
            df.at[df.index[i], "HTF_Score_Reason"] = reason
            df.at[df.index[i], self.output_column] = round(new_score, 5)

        return df

    def _safe_float(self, value, default=0.0) -> float:
        try:
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default