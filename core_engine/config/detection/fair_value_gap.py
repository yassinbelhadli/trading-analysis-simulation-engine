import pandas as pd
import numpy as np


class FVGDetector:
    def __init__(self, fvg_strength_min=0.10):
        self.fvg_strength_min = fvg_strength_min

    def calculate_atr(self, df: pd.DataFrame, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def process_fvg(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if "ATR" not in df.columns:
            df["ATR"] = self.calculate_atr(df)

        n = len(df)

        df["Bullish_FVG"] = False
        df["Bearish_FVG"] = False

        df["FVG_Upper"] = np.nan
        df["FVG_Lower"] = np.nan
        df["FVG_Midpoint"] = np.nan
        df["FVG_Size"] = np.nan
        df["FVG_Type"] = None
        df["FVG_ID"] = None
        df["FVG_Mitigated"] = False
        df["FVG_Fill_Index"] = np.nan
        df["FVG_Valid"] = False

        df["Active_FVG_Upper"] = np.nan
        df["Active_FVG_Lower"] = np.nan
        df["Active_FVG_Midpoint"] = np.nan
        df["Active_FVG_Size"] = np.nan
        df["Active_FVG_Type"] = None
        df["Active_FVG_ID"] = None
        df["Active_FVG_Age"] = 0
        df["Active_FVG_Valid"] = False

        highs = df["High"].values
        lows = df["Low"].values
        opens = df["Open"].values
        closes = df["Close"].values
        atrs = df["ATR"].values

        candle_bodies = np.abs(closes - opens)
        avg_body_arr = pd.Series(candle_bodies).rolling(window=14, min_periods=1).mean().values

        active_fvgs = []

        for i in range(2, n):
            atr = atrs[i]

            # ---------------------------------
            # 1. Create new FVG
            # ---------------------------------
            if not np.isnan(atr) and atr > 0:
                c1_body = candle_bodies[i - 2]
                c2_body = candle_bodies[i - 1]
                avg_body = avg_body_arr[i]

                # Candle 2 should be relatively small (inversion/pause candle)
                c2_is_small = avg_body <= 0 or c2_body <= avg_body * 1.2

                # Bullish FVG: Candle 1 bearish/neutral, Candle 3 bullish, gap up
                if (highs[i - 2] < lows[i] and c2_is_small
                        and closes[i] > opens[i]  # C3 bullish
                        and closes[i - 2] <= opens[i - 2]):  # C1 bearish or neutral
                    lower = highs[i - 2]
                    upper = lows[i]
                    size = upper - lower

                    if size >= atr * self.fvg_strength_min:
                        fvg_id = f"FVG_{df.index[i].strftime('%Y%m%d_%H%M')}"

                        df.at[df.index[i], "Bullish_FVG"] = True
                        df.at[df.index[i], "FVG_Lower"] = lower
                        df.at[df.index[i], "FVG_Upper"] = upper
                        df.at[df.index[i], "FVG_Midpoint"] = (upper + lower) / 2
                        df.at[df.index[i], "FVG_Size"] = size
                        df.at[df.index[i], "FVG_Type"] = "Bullish"
                        df.at[df.index[i], "FVG_ID"] = fvg_id
                        df.at[df.index[i], "FVG_Valid"] = True

                        active_fvgs.append({
                            "type": "Bullish",
                            "index": i,
                            "upper": upper,
                            "lower": lower,
                            "midpoint": (upper + lower) / 2,
                            "size": size,
                            "id": fvg_id,
                            "filled": False,
                            "fill_index": None,
                        })

                # Bearish FVG: Candle 1 bullish/neutral, Candle 3 bearish, gap down
                elif (lows[i - 2] > highs[i] and c2_is_small
                        and closes[i] < opens[i]  # C3 bearish
                        and closes[i - 2] >= opens[i - 2]):  # C1 bullish or neutral
                    upper = lows[i - 2]
                    lower = highs[i]
                    size = upper - lower

                    if size >= atr * self.fvg_strength_min:
                        fvg_id = f"FVG_{df.index[i].strftime('%Y%m%d_%H%M')}"

                        df.at[df.index[i], "Bearish_FVG"] = True
                        df.at[df.index[i], "FVG_Lower"] = lower
                        df.at[df.index[i], "FVG_Upper"] = upper
                        df.at[df.index[i], "FVG_Midpoint"] = (upper + lower) / 2
                        df.at[df.index[i], "FVG_Size"] = size
                        df.at[df.index[i], "FVG_Type"] = "Bearish"
                        df.at[df.index[i], "FVG_ID"] = fvg_id
                        df.at[df.index[i], "FVG_Valid"] = True

                        active_fvgs.append({
                            "type": "Bearish",
                            "index": i,
                            "upper": upper,
                            "lower": lower,
                            "midpoint": (upper + lower) / 2,
                            "size": size,
                            "id": fvg_id,
                            "filled": False,
                            "fill_index": None,
                        })

            # ---------------------------------
            # 2. Update FVG mitigation
            # ---------------------------------
            for zone in active_fvgs:
                if zone["filled"]:
                    continue

                if i <= zone["index"]:
                    continue

                if zone["type"] == "Bullish":
                    if lows[i] <= zone["lower"]:
                        zone["filled"] = True
                        zone["fill_index"] = i
                        df.at[df.index[zone["index"]], "FVG_Mitigated"] = True
                        df.at[df.index[zone["index"]], "FVG_Fill_Index"] = i

                elif zone["type"] == "Bearish":
                    if highs[i] >= zone["upper"]:
                        zone["filled"] = True
                        zone["fill_index"] = i
                        df.at[df.index[zone["index"]], "FVG_Mitigated"] = True
                        df.at[df.index[zone["index"]], "FVG_Fill_Index"] = i

            # ---------------------------------
            # 3. Write best active FVG to current row
            # ---------------------------------
            best_fvg = self._select_best_active_fvg(active_fvgs, closes[i])

            if best_fvg is not None:
                df.at[df.index[i], "Active_FVG_Upper"] = best_fvg["upper"]
                df.at[df.index[i], "Active_FVG_Lower"] = best_fvg["lower"]
                df.at[df.index[i], "Active_FVG_Midpoint"] = best_fvg["midpoint"]
                df.at[df.index[i], "Active_FVG_Size"] = best_fvg["size"]
                df.at[df.index[i], "Active_FVG_Type"] = best_fvg["type"]
                df.at[df.index[i], "Active_FVG_ID"] = best_fvg["id"]
                df.at[df.index[i], "Active_FVG_Age"] = i - best_fvg["index"]
                df.at[df.index[i], "Active_FVG_Valid"] = True

        return df

    def _select_best_active_fvg(self, active_fvgs, price):
        valid = [z for z in active_fvgs if not z["filled"]]

        if not valid:
            return None

        valid = sorted(
            valid,
            key=lambda z: abs(price - z["midpoint"])
        )

        return valid[0]

    def get_active_fvg(self, df: pd.DataFrame, price=None):
        active = df[
            (df["Active_FVG_Valid"] == True)
            & (df["Active_FVG_Lower"].notna())
            & (df["Active_FVG_Upper"].notna())
        ].copy()

        if price is not None:
            active = active[
                (active["Active_FVG_Lower"] <= price)
                & (price <= active["Active_FVG_Upper"])
            ]

        return active