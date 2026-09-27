import pandas as pd
import numpy as np


class LiquidityVoidDetector:
    """
    Liquidity Void Rules:

    Bullish Liquidity Void:
    - Candle closes bullish
    - Body >= ATR * body_atr_mult
    - Range >= ATR * range_atr_mult
    - Candle leaves fast one-sided movement
    - Stronger if aligned with Bullish FVG / Bullish VI / BOS / MSS

    Bearish Liquidity Void:
    - Candle closes bearish
    - Body >= ATR * body_atr_mult
    - Range >= ATR * range_atr_mult
    - Candle leaves fast one-sided movement
    - Stronger if aligned with Bearish FVG / Bearish VI / BOS / MSS

    Mitigation:
    - Bullish LV is mitigated when future price trades back below LV midpoint.
    - Bearish LV is mitigated when future price trades back above LV midpoint.
    """

    def __init__(
        self,
        body_atr_mult=1.20,
        range_atr_mult=1.50,
        min_strength=1.00,
        max_active_age=300
    ):
        self.body_atr_mult = body_atr_mult
        self.range_atr_mult = range_atr_mult
        self.min_strength = min_strength
        self.max_active_age = max_active_age

    def calculate_atr(self, df: pd.DataFrame, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()

    def process_liquidity_void(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if "ATR" not in df.columns:
            df["ATR"] = self.calculate_atr(df)

        n = len(df)

        bullish_lv = np.zeros(n, dtype=bool)
        bearish_lv = np.zeros(n, dtype=bool)

        lv_upper = np.full(n, np.nan)
        lv_lower = np.full(n, np.nan)
        lv_midpoint = np.full(n, np.nan)
        lv_size = np.full(n, np.nan)
        lv_strength = np.full(n, np.nan)

        lv_type = np.full(n, None, dtype=object)
        lv_id = np.full(n, None, dtype=object)
        lv_context = np.full(n, None, dtype=object)

        lv_valid = np.zeros(n, dtype=bool)
        lv_mitigated = np.zeros(n, dtype=bool)
        lv_fill_index = np.full(n, np.nan)
        lv_age = np.full(n, np.nan)

        opens = df["Open"].values
        highs = df["High"].values
        lows = df["Low"].values
        closes = df["Close"].values
        atrs = df["ATR"].values

        active_voids = []

        for i in range(20, n):
            atr = atrs[i]

            if np.isnan(atr) or atr <= 0:
                continue

            curr_open = opens[i]
            curr_high = highs[i]
            curr_low = lows[i]
            curr_close = closes[i]

            body = abs(curr_close - curr_open)
            candle_range = curr_high - curr_low

            if candle_range <= 0:
                continue

            body_ratio = body / atr
            range_ratio = candle_range / atr
            strength = (body_ratio * 0.60) + (range_ratio * 0.40)

            bullish_displacement = (
                curr_close > curr_open
                and body >= atr * self.body_atr_mult
                and candle_range >= atr * self.range_atr_mult
                and strength >= self.min_strength
            )

            bearish_displacement = (
                curr_close < curr_open
                and body >= atr * self.body_atr_mult
                and candle_range >= atr * self.range_atr_mult
                and strength >= self.min_strength
            )

            if bullish_displacement:
                lower = curr_open
                upper = curr_close
                midpoint = (upper + lower) / 2

                bullish_lv[i] = True
                lv_lower[i] = lower
                lv_upper[i] = upper
                lv_midpoint[i] = midpoint
                lv_size[i] = upper - lower
                lv_strength[i] = strength
                lv_type[i] = "Bullish"
                lv_id[i] = f"LV_{df.index[i].strftime('%Y%m%d_%H%M')}"
                lv_context[i] = self._detect_context(df, i, "Bullish")
                lv_valid[i] = self._validate_context(df, i, "Bullish", strength)

                active_voids.append({
                    "index": i,
                    "type": "Bullish",
                    "upper": upper,
                    "lower": lower,
                    "midpoint": midpoint,
                    "filled": False
                })

            elif bearish_displacement:
                upper = curr_open
                lower = curr_close
                midpoint = (upper + lower) / 2

                bearish_lv[i] = True
                lv_lower[i] = lower
                lv_upper[i] = upper
                lv_midpoint[i] = midpoint
                lv_size[i] = upper - lower
                lv_strength[i] = strength
                lv_type[i] = "Bearish"
                lv_id[i] = f"LV_{df.index[i].strftime('%Y%m%d_%H%M')}"
                lv_context[i] = self._detect_context(df, i, "Bearish")
                lv_valid[i] = self._validate_context(df, i, "Bearish", strength)

                active_voids.append({
                    "index": i,
                    "type": "Bearish",
                    "upper": upper,
                    "lower": lower,
                    "midpoint": midpoint,
                    "filled": False
                })

            for zone in active_voids:
                if zone["filled"]:
                    continue

                if i <= zone["index"]:
                    continue

                if i - zone["index"] > self.max_active_age:
                    continue

                if zone["type"] == "Bullish":
                    if lows[i] <= zone["midpoint"]:
                        lv_mitigated[zone["index"]] = True
                        lv_fill_index[zone["index"]] = i
                        lv_age[zone["index"]] = i - zone["index"]
                        zone["filled"] = True

                elif zone["type"] == "Bearish":
                    if highs[i] >= zone["midpoint"]:
                        lv_mitigated[zone["index"]] = True
                        lv_fill_index[zone["index"]] = i
                        lv_age[zone["index"]] = i - zone["index"]
                        zone["filled"] = True

        df["Bullish_LV"] = bullish_lv
        df["Bearish_LV"] = bearish_lv

        df["LV_Upper"] = lv_upper
        df["LV_Lower"] = lv_lower
        df["LV_Midpoint"] = lv_midpoint
        df["LV_Size"] = lv_size
        df["LV_Strength"] = lv_strength

        df["LV_Type"] = lv_type
        df["LV_ID"] = lv_id
        df["LV_Context"] = lv_context

        df["LV_Valid"] = lv_valid
        df["LV_Mitigated"] = lv_mitigated
        df["LV_Fill_Index"] = lv_fill_index
        df["LV_Age"] = lv_age

        return df

    def _detect_context(self, df: pd.DataFrame, i: int, direction: str):
        contexts = []

        if "MSS" in df.columns and df["MSS"].iloc[i] == True:
            contexts.append("MSS")

        if "CHoCH" in df.columns and df["CHoCH"].iloc[i] == True:
            contexts.append("CHoCH")

        if "BOS" in df.columns and df["BOS"].iloc[i] == True:
            contexts.append("BOS")

        if direction == "Bullish":
            if "Bullish_FVG" in df.columns and df["Bullish_FVG"].iloc[i] == True:
                contexts.append("FVG")
            if "Bullish_VI" in df.columns and df["Bullish_VI"].iloc[i] == True:
                contexts.append("VI")
            if "Bullish_OB" in df.columns and df["Bullish_OB"].iloc[i] == True:
                contexts.append("OB")

        elif direction == "Bearish":
            if "Bearish_FVG" in df.columns and df["Bearish_FVG"].iloc[i] == True:
                contexts.append("FVG")
            if "Bearish_VI" in df.columns and df["Bearish_VI"].iloc[i] == True:
                contexts.append("VI")
            if "Bearish_OB" in df.columns and df["Bearish_OB"].iloc[i] == True:
                contexts.append("OB")

        if "Valid_Sweep" in df.columns and df["Valid_Sweep"].iloc[i] == True:
            contexts.append("SWEEP")

        if not contexts:
            return "NONE"

        return "+".join(contexts)

    def _validate_context(self, df: pd.DataFrame, i: int, direction: str, strength: float):
        if strength >= 2.0:
            return True

        if "MSS" in df.columns and df["MSS"].iloc[i] == True:
            return True

        if "BOS" in df.columns and df["BOS"].iloc[i] == True:
            return True

        if direction == "Bullish":
            if "Bullish_FVG" in df.columns and df["Bullish_FVG"].iloc[i] == True:
                return True
            if "Bullish_VI" in df.columns and df["Bullish_VI"].iloc[i] == True:
                return True

        if direction == "Bearish":
            if "Bearish_FVG" in df.columns and df["Bearish_FVG"].iloc[i] == True:
                return True
            if "Bearish_VI" in df.columns and df["Bearish_VI"].iloc[i] == True:
                return True

        return False

    def get_active_voids(self, df: pd.DataFrame, price=None):
        active = df[
            (df["LV_Type"].notna()) &
            (df["LV_Mitigated"] == False)
        ].copy()

        if price is not None:
            active = active[
                (active["LV_Lower"] <= price) &
                (price <= active["LV_Upper"])
            ]

        return active