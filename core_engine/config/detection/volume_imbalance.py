import pandas as pd
import numpy as np


class VolumeImbalanceDetector:
    """
    Volume Imbalance Rules:

    Bullish Volume Imbalance:
    - Candle i closes bullish
    - Current candle open > previous candle close
    - Gap between previous close and current open
    - Gap size must be >= ATR * min_gap_atr_mult
    - Preferably after displacement / BOS / MSS / FVG

    Bearish Volume Imbalance:
    - Candle i closes bearish
    - Current candle open < previous candle close
    - Gap between current open and previous close
    - Gap size must be >= ATR * min_gap_atr_mult

    Mitigation:
    - Bullish VI is mitigated when future low trades back into the imbalance zone.
    - Bearish VI is mitigated when future high trades back into the imbalance zone.
    """

    def __init__(
        self,
        min_gap_atr_mult=0.02,
        max_active_age=200
    ):
        self.min_gap_atr_mult = min_gap_atr_mult
        self.max_active_age = max_active_age

    def calculate_atr(self, df: pd.DataFrame, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def process_volume_imbalance(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if "ATR" not in df.columns:
            df["ATR"] = self.calculate_atr(df)

        n = len(df)

        bullish_vi = np.zeros(n, dtype=bool)
        bearish_vi = np.zeros(n, dtype=bool)

        vi_upper = np.full(n, np.nan)
        vi_lower = np.full(n, np.nan)
        vi_midpoint = np.full(n, np.nan)
        vi_size = np.full(n, np.nan)

        vi_type = np.full(n, None, dtype=object)
        vi_id = np.full(n, None, dtype=object)

        vi_mitigated = np.zeros(n, dtype=bool)
        vi_fill_index = np.full(n, np.nan)
        vi_age = np.full(n, np.nan)

        vi_context = np.full(n, None, dtype=object)
        vi_valid = np.zeros(n, dtype=bool)
        vi_strength = np.full(n, np.nan)

        opens = df["Open"].values
        highs = df["High"].values
        lows = df["Low"].values
        closes = df["Close"].values
        atrs = df["ATR"].values

        active_zones = []

        for i in range(1, n):
            atr = atrs[i]

            if np.isnan(atr) or atr <= 0:
                continue

            prev_close = closes[i - 1]
            curr_open = opens[i]
            curr_close = closes[i]

            # -------------------------
            # Bullish Volume Imbalance
            # -------------------------
            if curr_open > prev_close and curr_close > curr_open:
                lower = prev_close
                upper = curr_open
                size = upper - lower

                if size >= atr * self.min_gap_atr_mult:
                    bullish_vi[i] = True
                    vi_lower[i] = lower
                    vi_upper[i] = upper
                    vi_midpoint[i] = (upper + lower) / 2
                    vi_size[i] = size
                    vi_type[i] = "Bullish"
                    vi_id[i] = f"VI_{df.index[i].strftime('%Y%m%d_%H%M')}"
                    vi_strength[i] = size / atr

                    vi_context[i] = self._detect_context(df, i, "Bullish")
                    vi_valid[i] = self._validate_context(df, i, "Bullish")

                    active_zones.append({
                        "index": i,
                        "type": "Bullish",
                        "upper": upper,
                        "lower": lower,
                        "filled": False
                    })

            # -------------------------
            # Bearish Volume Imbalance
            # -------------------------
            elif curr_open < prev_close and curr_close < curr_open:
                upper = prev_close
                lower = curr_open
                size = upper - lower

                if size >= atr * self.min_gap_atr_mult:
                    bearish_vi[i] = True
                    vi_lower[i] = lower
                    vi_upper[i] = upper
                    vi_midpoint[i] = (upper + lower) / 2
                    vi_size[i] = size
                    vi_type[i] = "Bearish"
                    vi_id[i] = f"VI_{df.index[i].strftime('%Y%m%d_%H%M')}"
                    vi_strength[i] = size / atr

                    vi_context[i] = self._detect_context(df, i, "Bearish")
                    vi_valid[i] = self._validate_context(df, i, "Bearish")

                    active_zones.append({
                        "index": i,
                        "type": "Bearish",
                        "upper": upper,
                        "lower": lower,
                        "filled": False
                    })

            # -------------------------
            # Mitigation Tracking
            # -------------------------
            for zone in active_zones:
                if zone["filled"]:
                    continue

                if i <= zone["index"]:
                    continue

                if i - zone["index"] > self.max_active_age:
                    continue

                if zone["type"] == "Bullish":
                    touched = lows[i] <= zone["upper"] and highs[i] >= zone["lower"]

                    if touched:
                        vi_mitigated[zone["index"]] = True
                        vi_fill_index[zone["index"]] = i
                        vi_age[zone["index"]] = i - zone["index"]
                        zone["filled"] = True

                elif zone["type"] == "Bearish":
                    touched = highs[i] >= zone["lower"] and lows[i] <= zone["upper"]

                    if touched:
                        vi_mitigated[zone["index"]] = True
                        vi_fill_index[zone["index"]] = i
                        vi_age[zone["index"]] = i - zone["index"]
                        zone["filled"] = True

        df["Bullish_VI"] = bullish_vi
        df["Bearish_VI"] = bearish_vi

        df["VI_Upper"] = vi_upper
        df["VI_Lower"] = vi_lower
        df["VI_Midpoint"] = vi_midpoint
        df["VI_Size"] = vi_size

        df["VI_Type"] = vi_type
        df["VI_ID"] = vi_id

        df["VI_Mitigated"] = vi_mitigated
        df["VI_Fill_Index"] = vi_fill_index
        df["VI_Age"] = vi_age

        df["VI_Context"] = vi_context
        df["VI_Strength"] = vi_strength
        df["VI_Valid"] = vi_valid

        return df

    def _detect_context(self, df: pd.DataFrame, i: int, direction: str):
        contexts = []

        if "MSS" in df.columns and df["MSS"].iloc[i] == True:
            contexts.append("MSS")

        if "BOS" in df.columns and df["BOS"].iloc[i] == True:
            contexts.append("BOS")

        if "CHoCH" in df.columns and df["CHoCH"].iloc[i] == True:
            contexts.append("CHoCH")

        if direction == "Bullish":
            if "Bullish_FVG" in df.columns and df["Bullish_FVG"].iloc[i] == True:
                contexts.append("FVG")
            if "Liquidity_Sweep" in df.columns and df["Liquidity_Sweep"].iloc[i] == True:
                contexts.append("LIQUIDITY")
            if "OB_Type" in df.columns and df["OB_Type"].iloc[i] == "Bullish":
                contexts.append("OB")

        elif direction == "Bearish":
            if "Bearish_FVG" in df.columns and df["Bearish_FVG"].iloc[i] == True:
                contexts.append("FVG")
            if "Liquidity_Sweep" in df.columns and df["Liquidity_Sweep"].iloc[i] == True:
                contexts.append("LIQUIDITY")
            if "OB_Type" in df.columns and df["OB_Type"].iloc[i] == "Bearish":
                contexts.append("OB")

        if not contexts:
            return "NONE"

        return "+".join(contexts)

    def _validate_context(self, df: pd.DataFrame, i: int, direction: str):
        has_structure = False
        has_fvg = False
        has_liquidity = False

        if "MSS" in df.columns and df["MSS"].iloc[i] == True:
            has_structure = True

        if "BOS" in df.columns and df["BOS"].iloc[i] == True:
            has_structure = True

        if direction == "Bullish":
            if "Bullish_FVG" in df.columns and df["Bullish_FVG"].iloc[i] == True:
                has_fvg = True

        if direction == "Bearish":
            if "Bearish_FVG" in df.columns and df["Bearish_FVG"].iloc[i] == True:
                has_fvg = True

        if "Valid_Sweep" in df.columns and df["Valid_Sweep"].iloc[i] == True:
            has_liquidity = True

        return has_structure or has_fvg or has_liquidity

    def get_active_imbalances(self, df: pd.DataFrame, price=None):
        active = df[
            (df["VI_Type"].notna()) &
            (df["VI_Mitigated"] == False)
        ].copy()

        if price is not None:
            active = active[
                (active["VI_Lower"] <= price) &
                (price <= active["VI_Upper"])
            ]

        return active