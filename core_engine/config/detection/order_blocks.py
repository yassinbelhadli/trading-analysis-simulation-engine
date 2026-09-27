import pandas as pd
import numpy as np


class OrderBlockEngine:
    def __init__(self, body_multiplier=1.2, ob_max_touches=2):
        self.body_multiplier = body_multiplier
        self.ob_max_touches = ob_max_touches

    def _get_atr(self, df: pd.DataFrame):
        if "ATR" in df.columns:
            return df["ATR"]

        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(14).mean()

    def _classify_context(self, df: pd.DataFrame, i: int, direction: str, window: int = 5):
        lookback = max(0, i - window)
        for j in range(i, lookback - 1, -1):
            if "MSS" in df.columns and df["MSS"].iloc[j] == True:
                return "MSS_BULLISH" if direction == "bullish" else "MSS_BEARISH"
        for j in range(i, lookback - 1, -1):
            if "CHoCH" in df.columns and df["CHoCH"].iloc[j] == True:
                return "CHoCH_BULLISH" if direction == "bullish" else "CHoCH_BEARISH"
        for j in range(i, lookback - 1, -1):
            if "BOS" in df.columns and df["BOS"].iloc[j] == True:
                return "BOS_BULLISH" if direction == "bullish" else "BOS_BEARISH"
        return "NONE"

    def detect_order_blocks(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if "ATR" not in df.columns:
            df["ATR"] = self._get_atr(df)

        n = len(df)

        df["Bullish_OB"] = False
        df["Bearish_OB"] = False

        df["OB_Upper"] = np.nan
        df["OB_Lower"] = np.nan
        df["OB_Midpoint"] = np.nan
        df["OB_Size"] = np.nan

        df["OB_Type"] = None
        df["OB_ID"] = None
        df["OB_Context"] = None

        df["OB_Mitigated"] = False
        df["OB_Touches"] = 0
        df["OB_Liquidity_Score"] = 0
        df["OB_Valid"] = False

        df["Active_OB_Upper"] = np.nan
        df["Active_OB_Lower"] = np.nan
        df["Active_OB_Midpoint"] = np.nan
        df["Active_OB_Type"] = None
        df["Active_OB_ID"] = None
        df["Active_OB_Context"] = None
        df["Active_OB_Touches"] = 0
        df["Active_OB_Valid"] = False

        highs = df["High"].values
        lows = df["Low"].values
        opens = df["Open"].values
        closes = df["Close"].values
        atrs = df["ATR"].values

        active_obs = []

        for i in range(2, n):
            atr = atrs[i]

            # -----------------------------
            # 1. Create new OB
            # -----------------------------
            if not np.isnan(atr) and atr > 0:
                body = abs(closes[i] - opens[i])

                if body >= atr * self.body_multiplier:
                    bullish_break = closes[i] > opens[i]
                    bearish_break = closes[i] < opens[i]

                    if bullish_break and closes[i - 1] < opens[i - 1]:
                        ob_index = i - 1
                        upper = highs[ob_index]
                        lower = lows[ob_index]
                        context = self._classify_context(df, i, "bullish")

                        ob = {
                            "index": ob_index,
                            "type": "Bullish",
                            "upper": upper,
                            "lower": lower,
                            "midpoint": (upper + lower) / 2,
                            "size": upper - lower,
                            "id": f"BOB_{df.index[ob_index].strftime('%Y%m%d_%H%M')}",
                            "context": context,
                            "touches": 0,
                            "mitigated": False,
                            "last_touch_index": None,
                        }

                        active_obs.append(ob)

                        df.at[df.index[ob_index], "Bullish_OB"] = True
                        df.at[df.index[ob_index], "OB_Upper"] = upper
                        df.at[df.index[ob_index], "OB_Lower"] = lower
                        df.at[df.index[ob_index], "OB_Midpoint"] = ob["midpoint"]
                        df.at[df.index[ob_index], "OB_Size"] = ob["size"]
                        df.at[df.index[ob_index], "OB_Type"] = "Bullish"
                        df.at[df.index[ob_index], "OB_ID"] = ob["id"]
                        df.at[df.index[ob_index], "OB_Context"] = context

                    elif bearish_break and closes[i - 1] > opens[i - 1]:
                        ob_index = i - 1
                        upper = highs[ob_index]
                        lower = lows[ob_index]
                        context = self._classify_context(df, i, "bearish")

                        ob = {
                            "index": ob_index,
                            "type": "Bearish",
                            "upper": upper,
                            "lower": lower,
                            "midpoint": (upper + lower) / 2,
                            "size": upper - lower,
                            "id": f"SOB_{df.index[ob_index].strftime('%Y%m%d_%H%M')}",
                            "context": context,
                            "touches": 0,
                            "mitigated": False,
                            "last_touch_index": None,
                        }

                        active_obs.append(ob)

                        df.at[df.index[ob_index], "Bearish_OB"] = True
                        df.at[df.index[ob_index], "OB_Upper"] = upper
                        df.at[df.index[ob_index], "OB_Lower"] = lower
                        df.at[df.index[ob_index], "OB_Midpoint"] = ob["midpoint"]
                        df.at[df.index[ob_index], "OB_Size"] = ob["size"]
                        df.at[df.index[ob_index], "OB_Type"] = "Bearish"
                        df.at[df.index[ob_index], "OB_ID"] = ob["id"]
                        df.at[df.index[ob_index], "OB_Context"] = context

            # -----------------------------
            # 2. Update active OBs
            # -----------------------------
            curr_high = highs[i]
            curr_low = lows[i]
            curr_close = closes[i]

            for ob in active_obs:
                if ob["mitigated"]:
                    continue

                if i <= ob["index"] + 2:
                    continue

                touched = curr_low <= ob["upper"] and curr_high >= ob["lower"]

                if touched and ob["last_touch_index"] != i:
                    ob["touches"] += 1
                    ob["last_touch_index"] = i
                    df.at[df.index[ob["index"]], "OB_Touches"] = ob["touches"]

                mit_buf = max(ob["size"] * 0.15, atr * 0.08) if not np.isnan(atr) and atr > 0 else ob["size"] * 0.15

                if ob["type"] == "Bullish" and curr_close < ob["lower"] - mit_buf:
                    ob["mitigated"] = True
                    df.at[df.index[ob["index"]], "OB_Mitigated"] = True
                    continue

                if ob["type"] == "Bearish" and curr_close > ob["upper"] + mit_buf:
                    ob["mitigated"] = True
                    df.at[df.index[ob["index"]], "OB_Mitigated"] = True
                    continue

            # -----------------------------
            # 3. Write best active OB to current row
            # -----------------------------
            best_ob = self._select_best_active_ob(active_obs, curr_close)

            if best_ob is not None:
                df.at[df.index[i], "Active_OB_Upper"] = best_ob["upper"]
                df.at[df.index[i], "Active_OB_Lower"] = best_ob["lower"]
                df.at[df.index[i], "Active_OB_Midpoint"] = best_ob["midpoint"]
                df.at[df.index[i], "Active_OB_Type"] = best_ob["type"]
                df.at[df.index[i], "Active_OB_ID"] = best_ob["id"]
                df.at[df.index[i], "Active_OB_Context"] = best_ob["context"]
                df.at[df.index[i], "Active_OB_Touches"] = best_ob["touches"]
                df.at[df.index[i], "Active_OB_Valid"] = True

        df = self.liquidity_filter(df)

        df["OB_Valid"] = (
            df["OB_Type"].notna()
            & (df["OB_Mitigated"] == False)
        )

        return df

    def _select_best_active_ob(self, active_obs, price):
        valid_obs = [
            ob for ob in active_obs
            if not ob["mitigated"]
        ]

        if not valid_obs:
            return None

        # Prefer closest active OB midpoint to current price
        valid_obs = sorted(
            valid_obs,
            key=lambda ob: abs(price - ob["midpoint"])
        )

        return valid_obs[0]

    def liquidity_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        if "Liquidity_Sweep" not in df.columns:
            return df

        for i in range(len(df)):
            score = 0

            if df["Liquidity_Sweep"].iloc[i] == True:
                score += 2

            if "Valid_Sweep" in df.columns and df["Valid_Sweep"].iloc[i] == True:
                score += 3

            if "Sweep_Strength" in df.columns:
                strength = df["Sweep_Strength"].iloc[i]
                if pd.notna(strength) and strength > 1:
                    score += 2

            df.at[df.index[i], "OB_Liquidity_Score"] = score

        return df

    def process_order_blocks(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.detect_order_blocks(df)