import pandas as pd
import numpy as np


class SupportResistanceDetector:
    def __init__(
        self,
        sr_tolerance_atr_mult=0.30,
        lookback=120,
        min_touches=2,
        max_levels_memory=40,
        break_buffer_atr_mult=0.08
    ):
        self.sr_tolerance_atr_mult = sr_tolerance_atr_mult
        self.lookback = lookback
        self.min_touches = min_touches
        self.max_levels_memory = max_levels_memory
        self.break_buffer_atr_mult = break_buffer_atr_mult

    def calculate_atr(self, df: pd.DataFrame, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()

    def _merge_level(self, levels, price, index, tolerance):
        for level in levels:
            if abs(level["price"] - price) <= tolerance:
                level["price"] = (level["price"] + price) / 2
                level["touches"] += 1
                level["last_index"] = index
                return levels

        levels.append({
            "price": price,
            "index": index,
            "last_index": index,
            "touches": 1,
            "broken": False
        })

        if len(levels) > self.max_levels_memory:
            levels.pop(0)

        return levels

    def process_support_resistance(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if "ATR" not in df.columns:
            df["ATR"] = self.calculate_atr(df)

        n = len(df)

        df["Support_Level"] = np.nan
        df["Resistance_Level"] = np.nan
        df["Near_Support"] = False
        df["Near_Resistance"] = False
        df["Support_Touches"] = 0
        df["Resistance_Touches"] = 0
        df["Support_Broken"] = False
        df["Resistance_Broken"] = False
        df["SR_State"] = "NONE"
        df["SR_ID"] = None
        df["SR_Strength"] = 0.0
        df["SR_Distance_ATR"] = np.nan
        df["SR_Valid_Buy"] = False
        df["SR_Valid_Sell"] = False

        highs = df["High"].values
        lows = df["Low"].values
        closes = df["Close"].values
        atrs = df["ATR"].values

        swing_highs = (
            df["Confirmed_Swing_High"].values
            if "Confirmed_Swing_High" in df.columns
            else np.full(n, np.nan)
        )

        swing_lows = (
            df["Confirmed_Swing_Low"].values
            if "Confirmed_Swing_Low" in df.columns
            else np.full(n, np.nan)
        )

        resistance_levels = []
        support_levels = []

        for i in range(n):
            atr = atrs[i]

            if np.isnan(atr) or atr <= 0:
                continue

            tolerance = atr * self.sr_tolerance_atr_mult
            break_buffer = atr * self.break_buffer_atr_mult
            close = closes[i]

            if not np.isnan(swing_highs[i]):
                resistance_levels = self._merge_level(
                    resistance_levels,
                    swing_highs[i],
                    i,
                    tolerance
                )

            if not np.isnan(swing_lows[i]):
                support_levels = self._merge_level(
                    support_levels,
                    swing_lows[i],
                    i,
                    tolerance
                )

            best_support = None
            best_resistance = None

            for level in support_levels:
                if level["broken"]:
                    continue

                if i <= level["index"]:
                    continue

                if close < level["price"] - break_buffer:
                    level["broken"] = True
                    df.at[df.index[i], "Support_Broken"] = True
                    continue

                if lows[i] <= level["price"] + tolerance and highs[i] >= level["price"] - tolerance:
                    if level["last_index"] != i:
                        level["touches"] += 1
                        level["last_index"] = i

                if level["price"] <= close:
                    if best_support is None or level["price"] > best_support["price"]:
                        best_support = level

            for level in resistance_levels:
                if level["broken"]:
                    continue

                if i <= level["index"]:
                    continue

                if close > level["price"] + break_buffer:
                    level["broken"] = True
                    df.at[df.index[i], "Resistance_Broken"] = True
                    continue

                if highs[i] >= level["price"] - tolerance and lows[i] <= level["price"] + tolerance:
                    if level["last_index"] != i:
                        level["touches"] += 1
                        level["last_index"] = i

                if level["price"] >= close:
                    if best_resistance is None or level["price"] < best_resistance["price"]:
                        best_resistance = level

            near_support = False
            near_resistance = False
            support_distance_atr = np.nan
            resistance_distance_atr = np.nan

            if best_support is not None:
                support_price = best_support["price"]
                support_distance = abs(close - support_price)
                support_distance_atr = support_distance / atr

                df.at[df.index[i], "Support_Level"] = support_price
                df.at[df.index[i], "Support_Touches"] = best_support["touches"]

                if support_distance <= tolerance:
                    near_support = True
                    df.at[df.index[i], "Near_Support"] = True

            if best_resistance is not None:
                resistance_price = best_resistance["price"]
                resistance_distance = abs(resistance_price - close)
                resistance_distance_atr = resistance_distance / atr

                df.at[df.index[i], "Resistance_Level"] = resistance_price
                df.at[df.index[i], "Resistance_Touches"] = best_resistance["touches"]

                if resistance_distance <= tolerance:
                    near_resistance = True
                    df.at[df.index[i], "Near_Resistance"] = True

            if near_support and not near_resistance:
                df.at[df.index[i], "SR_State"] = "SUPPORT"
                df.at[df.index[i], "SR_Distance_ATR"] = support_distance_atr

            elif near_resistance and not near_support:
                df.at[df.index[i], "SR_State"] = "RESISTANCE"
                df.at[df.index[i], "SR_Distance_ATR"] = resistance_distance_atr

            elif near_support and near_resistance:
                df.at[df.index[i], "SR_State"] = "RANGE_COMPRESSION"
                df.at[df.index[i], "SR_Distance_ATR"] = min(
                    support_distance_atr if not np.isnan(support_distance_atr) else 999,
                    resistance_distance_atr if not np.isnan(resistance_distance_atr) else 999
                )

            support_touches = int(df.at[df.index[i], "Support_Touches"])
            resistance_touches = int(df.at[df.index[i], "Resistance_Touches"])

            strength = 0.0

            if support_touches >= self.min_touches:
                strength += min(support_touches, 5)

            if resistance_touches >= self.min_touches:
                strength += min(resistance_touches, 5)

            if "Liquidity_Sweep" in df.columns and df["Liquidity_Sweep"].iloc[i] == True:
                strength += 2

            if "Valid_Sweep" in df.columns and df["Valid_Sweep"].iloc[i] == True:
                strength += 2

            if "BOS" in df.columns and df["BOS"].iloc[i] == True:
                strength += 2

            if "CHoCH" in df.columns and df["CHoCH"].iloc[i] == True:
                strength += 2

            if "MSS" in df.columns and df["MSS"].iloc[i] == True:
                strength += 3

            df.at[df.index[i], "SR_Strength"] = min(strength, 10)

            bullish_context = (
                "BULLISH" in str(df["Market_Trend"].iloc[i])
                if "Market_Trend" in df.columns
                else False
            )

            bearish_context = (
                "BEARISH" in str(df["Market_Trend"].iloc[i])
                if "Market_Trend" in df.columns
                else False
            )

            if near_support and bullish_context and strength >= self.min_touches:
                df.at[df.index[i], "SR_Valid_Buy"] = True

            if near_resistance and bearish_context and strength >= self.min_touches:
                df.at[df.index[i], "SR_Valid_Sell"] = True

            df.at[df.index[i], "SR_ID"] = f"SR_{df.index[i].strftime('%Y%m%d_%H%M')}"

        return df

    def get_latest_sr(self, df: pd.DataFrame):
        latest = df.iloc[-1]

        return {
            "support": latest.get("Support_Level", np.nan),
            "resistance": latest.get("Resistance_Level", np.nan),
            "state": latest.get("SR_State", None),
            "strength": latest.get("SR_Strength", 0),
            "distance_atr": latest.get("SR_Distance_ATR", np.nan),
            "valid_buy": latest.get("SR_Valid_Buy", False),
            "valid_sell": latest.get("SR_Valid_Sell", False),
        }