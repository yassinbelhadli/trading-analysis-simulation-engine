import pandas as pd
import numpy as np


class CandlePatternDetector:
    def __init__(
        self,
        strong_body_atr_mult=0.60,
        rejection_wick_ratio=2.0,
        doji_body_ratio=0.15,
        engulfing_min_body_ratio=1.05
    ):
        self.strong_body_atr_mult = strong_body_atr_mult
        self.rejection_wick_ratio = rejection_wick_ratio
        self.doji_body_ratio = doji_body_ratio
        self.engulfing_min_body_ratio = engulfing_min_body_ratio

    def calculate_atr(self, df: pd.DataFrame, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()

    def process_candle_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if "ATR" not in df.columns:
            df["ATR"] = self.calculate_atr(df)

        n = len(df)

        df["Bullish_Engulfing"] = False
        df["Bearish_Engulfing"] = False

        df["Bullish_Rejection"] = False
        df["Bearish_Rejection"] = False

        df["Strong_Bullish_Close"] = False
        df["Strong_Bearish_Close"] = False

        df["Inside_Bar"] = False
        df["Doji"] = False

        df["Candle_Pattern"] = None
        df["Candle_Direction"] = None
        df["Candle_Strength"] = 0.0

        df["Candle_Valid_Buy"] = False
        df["Candle_Valid_Sell"] = False
        df["Candle_ID"] = None

        opens = df["Open"].values
        highs = df["High"].values
        lows = df["Low"].values
        closes = df["Close"].values
        atrs = df["ATR"].values

        for i in range(1, n):
            atr = atrs[i]

            if np.isnan(atr) or atr <= 0:
                continue

            open_ = opens[i]
            high = highs[i]
            low = lows[i]
            close = closes[i]

            prev_open = opens[i - 1]
            prev_close = closes[i - 1]
            prev_high = highs[i - 1]
            prev_low = lows[i - 1]

            body = abs(close - open_)
            candle_range = high - low

            if candle_range <= 0:
                continue

            upper_wick = high - max(open_, close)
            lower_wick = min(open_, close) - low

            bullish = close > open_
            bearish = close < open_

            prev_bullish = prev_close > prev_open
            prev_bearish = prev_close < prev_open
            prev_body = abs(prev_close - prev_open)

            patterns = []
            direction = None
            strength = 0.0

            # -------------------------
            # Bullish Engulfing
            # -------------------------
            if (
                bullish
                and prev_bearish
                and close >= prev_open
                and open_ <= prev_close
                and body >= prev_body * self.engulfing_min_body_ratio
            ):
                df.at[df.index[i], "Bullish_Engulfing"] = True
                patterns.append("Bullish_Engulfing")
                direction = "Bullish"
                strength += 3.0

            # -------------------------
            # Bearish Engulfing
            # -------------------------
            if (
                bearish
                and prev_bullish
                and close <= prev_open
                and open_ >= prev_close
                and body >= prev_body * self.engulfing_min_body_ratio
            ):
                df.at[df.index[i], "Bearish_Engulfing"] = True
                patterns.append("Bearish_Engulfing")
                direction = "Bearish"
                strength += 3.0

            # -------------------------
            # Bullish Rejection / Pin Bar
            # -------------------------
            if (
                lower_wick >= body * self.rejection_wick_ratio
                and lower_wick > upper_wick
                and close > low + candle_range * 0.50
            ):
                df.at[df.index[i], "Bullish_Rejection"] = True
                patterns.append("Bullish_Rejection")
                direction = "Bullish"
                strength += 2.0

            # -------------------------
            # Bearish Rejection / Pin Bar
            # -------------------------
            if (
                upper_wick >= body * self.rejection_wick_ratio
                and upper_wick > lower_wick
                and close < high - candle_range * 0.50
            ):
                df.at[df.index[i], "Bearish_Rejection"] = True
                patterns.append("Bearish_Rejection")
                direction = "Bearish"
                strength += 2.0

            # -------------------------
            # Strong Bullish Close
            # -------------------------
            if (
                bullish
                and body >= atr * self.strong_body_atr_mult
                and close >= low + candle_range * 0.70
            ):
                df.at[df.index[i], "Strong_Bullish_Close"] = True
                patterns.append("Strong_Bullish_Close")
                direction = "Bullish"
                strength += 2.5

            # -------------------------
            # Strong Bearish Close
            # -------------------------
            if (
                bearish
                and body >= atr * self.strong_body_atr_mult
                and close <= high - candle_range * 0.70
            ):
                df.at[df.index[i], "Strong_Bearish_Close"] = True
                patterns.append("Strong_Bearish_Close")
                direction = "Bearish"
                strength += 2.5

            # -------------------------
            # Inside Bar
            # -------------------------
            if high <= prev_high and low >= prev_low:
                df.at[df.index[i], "Inside_Bar"] = True
                patterns.append("Inside_Bar")
                strength += 0.5

            # -------------------------
            # Doji / Indecision
            # -------------------------
            if body <= candle_range * self.doji_body_ratio:
                df.at[df.index[i], "Doji"] = True
                patterns.append("Doji")
                strength += 0.3

            # -------------------------
            # Context Boosts
            # -------------------------
            if patterns:
                if "Valid_Sweep" in df.columns and df["Valid_Sweep"].iloc[i] == True:
                    strength += 1.5

                if "MSS" in df.columns and df["MSS"].iloc[i] == True:
                    strength += 2.0

                if "CHoCH" in df.columns and df["CHoCH"].iloc[i] == True:
                    strength += 1.5

                if "BOS" in df.columns and df["BOS"].iloc[i] == True:
                    strength += 1.0

                if direction == "Bullish":
                    if "PD_Valid_Buy" in df.columns and df["PD_Valid_Buy"].iloc[i] == True:
                        strength += 1.0
                    if "Near_Support" in df.columns and df["Near_Support"].iloc[i] == True:
                        strength += 1.0
                    if "Bullish_FVG" in df.columns and df["Bullish_FVG"].iloc[i] == True:
                        strength += 1.0
                    if "Bullish_OB" in df.columns and df["Bullish_OB"].iloc[i] == True:
                        strength += 1.0

                if direction == "Bearish":
                    if "PD_Valid_Sell" in df.columns and df["PD_Valid_Sell"].iloc[i] == True:
                        strength += 1.0
                    if "Near_Resistance" in df.columns and df["Near_Resistance"].iloc[i] == True:
                        strength += 1.0
                    if "Bearish_FVG" in df.columns and df["Bearish_FVG"].iloc[i] == True:
                        strength += 1.0
                    if "Bearish_OB" in df.columns and df["Bearish_OB"].iloc[i] == True:
                        strength += 1.0

                df.at[df.index[i], "Candle_Pattern"] = "+".join(patterns)
                df.at[df.index[i], "Candle_Direction"] = direction
                df.at[df.index[i], "Candle_Strength"] = min(strength, 10)
                df.at[df.index[i], "Candle_ID"] = f"CANDLE_{df.index[i].strftime('%Y%m%d_%H%M')}"

                if direction == "Bullish" and strength >= 3.0:
                    df.at[df.index[i], "Candle_Valid_Buy"] = True

                if direction == "Bearish" and strength >= 3.0:
                    df.at[df.index[i], "Candle_Valid_Sell"] = True

        return df

    def get_latest_pattern(self, df: pd.DataFrame):
        latest = df.iloc[-1]

        return {
            "pattern": latest.get("Candle_Pattern", None),
            "direction": latest.get("Candle_Direction", None),
            "strength": latest.get("Candle_Strength", 0),
            "valid_buy": latest.get("Candle_Valid_Buy", False),
            "valid_sell": latest.get("Candle_Valid_Sell", False),
        }