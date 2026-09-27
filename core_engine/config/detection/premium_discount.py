import pandas as pd
import numpy as np


class PremiumDiscountDetector:
    def __init__(
        self,
        equilibrium_tolerance=0.05,
        use_protected_levels=True,
        lookback_range=100
    ):
        self.equilibrium_tolerance = equilibrium_tolerance
        self.use_protected_levels = use_protected_levels
        self.lookback_range = lookback_range

    def process_premium_discount(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        n = len(df)

        df["PD_Range_High"] = np.nan
        df["PD_Range_Low"] = np.nan
        df["EQ_Level"] = np.nan

        df["Premium_Zone"] = False
        df["Discount_Zone"] = False
        df["Equilibrium_Zone"] = False

        df["PD_State"] = None
        df["PD_Valid_Buy"] = False
        df["PD_Valid_Sell"] = False
        df["PD_Position"] = np.nan
        df["PD_ID"] = None

        highs = df["High"].values
        lows = df["Low"].values
        closes = df["Close"].values

        protected_high = (
            df["Protected_High_Level"].values
            if "Protected_High_Level" in df.columns
            else np.full(n, np.nan)
        )

        protected_low = (
            df["Protected_Low_Level"].values
            if "Protected_Low_Level" in df.columns
            else np.full(n, np.nan)
        )

        trend = (
            df["Market_Trend"].values
            if "Market_Trend" in df.columns
            else np.full(n, "NEUTRAL", dtype=object)
        )

        for i in range(n):
            range_high = np.nan
            range_low = np.nan

            if self.use_protected_levels:
                ph = protected_high[i]
                pl = protected_low[i]

                if not np.isnan(ph) and not np.isnan(pl) and ph > pl:
                    range_high = ph
                    range_low = pl

            if np.isnan(range_high) or np.isnan(range_low):
                start = max(0, i - self.lookback_range)
                range_high = np.max(highs[start:i + 1])
                range_low = np.min(lows[start:i + 1])

            if np.isnan(range_high) or np.isnan(range_low) or range_high <= range_low:
                continue

            eq = (range_high + range_low) / 2
            current_close = closes[i]
            total_range = range_high - range_low

            position = (current_close - range_low) / total_range

            tolerance_zone = self.equilibrium_tolerance

            df.at[df.index[i], "PD_Range_High"] = range_high
            df.at[df.index[i], "PD_Range_Low"] = range_low
            df.at[df.index[i], "EQ_Level"] = eq
            df.at[df.index[i], "PD_Position"] = position
            df.at[df.index[i], "PD_ID"] = f"PD_{df.index[i].strftime('%Y%m%d_%H%M')}"

            if position > 0.5 + tolerance_zone:
                df.at[df.index[i], "Premium_Zone"] = True
                df.at[df.index[i], "PD_State"] = "PREMIUM"

            elif position < 0.5 - tolerance_zone:
                df.at[df.index[i], "Discount_Zone"] = True
                df.at[df.index[i], "PD_State"] = "DISCOUNT"

            else:
                df.at[df.index[i], "Equilibrium_Zone"] = True
                df.at[df.index[i], "PD_State"] = "EQUILIBRIUM"

            is_bullish_context = (
                "BULLISH" in str(trend[i])
                or ("MSS_Type" in df.columns and df["MSS_Type"].iloc[i] == "Bullish")
                or ("CHoCH_Type" in df.columns and df["CHoCH_Type"].iloc[i] == "Bullish")
                or ("BOS_Type" in df.columns and df["BOS_Type"].iloc[i] == "Bullish")
            )

            is_bearish_context = (
                "BEARISH" in str(trend[i])
                or ("MSS_Type" in df.columns and df["MSS_Type"].iloc[i] == "Bearish")
                or ("CHoCH_Type" in df.columns and df["CHoCH_Type"].iloc[i] == "Bearish")
                or ("BOS_Type" in df.columns and df["BOS_Type"].iloc[i] == "Bearish")
            )

            if df.at[df.index[i], "Discount_Zone"] and is_bullish_context:
                df.at[df.index[i], "PD_Valid_Buy"] = True

            if df.at[df.index[i], "Premium_Zone"] and is_bearish_context:
                df.at[df.index[i], "PD_Valid_Sell"] = True

        return df

    def get_pd_summary(self, df: pd.DataFrame):
        if "PD_State" not in df.columns:
            return {}

        latest = df.iloc[-1]

        return {
            "state": latest["PD_State"],
            "range_high": latest["PD_Range_High"],
            "range_low": latest["PD_Range_Low"],
            "equilibrium": latest["EQ_Level"],
            "position": latest["PD_Position"],
            "valid_buy": latest["PD_Valid_Buy"],
            "valid_sell": latest["PD_Valid_Sell"],
        }