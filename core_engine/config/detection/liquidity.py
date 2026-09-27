import pandas as pd
import numpy as np


class LiquidityEngine:
    def __init__(
        self,
        eq_tolerance_atr_mult=0.10,
        asian_session_start="00:00",
        asian_session_end="06:00",
        displacement_multiplier=1.2,
        max_sweep_strength=10.0
    ):
        self.eq_tolerance_atr_mult = eq_tolerance_atr_mult
        self.asian_start = asian_session_start
        self.asian_end = asian_session_end
        self.displacement_multiplier = displacement_multiplier
        self.max_sweep_strength = max_sweep_strength

    def calculate_atr(self, df: pd.DataFrame, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()

    def detect_equal_levels(self, df: pd.DataFrame):
        n = len(df)

        eqh = np.zeros(n, dtype=bool)
        eql = np.zeros(n, dtype=bool)

        active_eqh_price = np.full(n, np.nan)
        active_eql_price = np.full(n, np.nan)

        pool_count = np.zeros(n, dtype=int)
        liquidity_age = np.full(n, np.nan)

        recent_highs = []
        recent_lows = []

        if "Confirmed_Swing_High" not in df.columns or "Confirmed_Swing_Low" not in df.columns:
            raise ValueError("Missing Confirmed_Swing_High / Confirmed_Swing_Low from market_structure.py")

        highs = df["Confirmed_Swing_High"].values
        lows = df["Confirmed_Swing_Low"].values
        atrs = df["ATR"].values

        last_eqh_price = np.nan
        last_eql_price = np.nan
        last_eqh_index = None
        last_eql_index = None

        for i in range(n):
            atr = atrs[i]
            if np.isnan(atr) or atr <= 0:
                active_eqh_price[i] = last_eqh_price
                active_eql_price[i] = last_eql_price
                continue

            tolerance = max(atr * self.eq_tolerance_atr_mult, 1e-5)

            if not np.isnan(highs[i]):
                h = highs[i]
                matches = [prev for prev in recent_highs if abs(h - prev[0]) <= tolerance]

                if matches:
                    eqh[i] = True
                    all_prices = [m[0] for m in matches] + [h]
                    last_eqh_price = float(np.mean(all_prices))
                    last_eqh_index = matches[0][1]
                    pool_count[i] = len(matches) + 1

                recent_highs.append((h, i))
                if len(recent_highs) > 20:
                    recent_highs.pop(0)

            if not np.isnan(lows[i]):
                l = lows[i]
                matches = [prev for prev in recent_lows if abs(l - prev[0]) <= tolerance]

                if matches:
                    eql[i] = True
                    all_prices = [m[0] for m in matches] + [l]
                    last_eql_price = float(np.mean(all_prices))
                    last_eql_index = matches[0][1]
                    pool_count[i] = max(pool_count[i], len(matches) + 1)

                recent_lows.append((l, i))
                if len(recent_lows) > 20:
                    recent_lows.pop(0)

            active_eqh_price[i] = last_eqh_price
            active_eql_price[i] = last_eql_price

            if last_eqh_index is not None:
                liquidity_age[i] = i - last_eqh_index
            if last_eql_index is not None:
                liquidity_age[i] = max(liquidity_age[i] if not np.isnan(liquidity_age[i]) else 0, i - last_eql_index)

        df["EQH"] = eqh
        df["EQL"] = eql
        df["EQH_Price"] = active_eqh_price
        df["EQL_Price"] = active_eql_price
        df["Pool_Count"] = pool_count
        df["Liquidity_Age"] = liquidity_age

        return df

    def detect_time_based_liquidity(self, df: pd.DataFrame):
        df = df.copy()
        df["Date"] = df.index.date

        daily = df.groupby("Date").agg({"High": "max", "Low": "min"})
        daily["PDH"] = daily["High"].shift(1)
        daily["PDL"] = daily["Low"].shift(1)

        df = df.merge(daily[["PDH", "PDL"]], left_on="Date", right_index=True, how="left")

        df["Time"] = df.index.time

        asian_start = pd.to_datetime(self.asian_start).time()
        asian_end = pd.to_datetime(self.asian_end).time()

        asian = df[(df["Time"] >= asian_start) & (df["Time"] <= asian_end)]
        asian_range = asian.groupby("Date").agg({"High": "max", "Low": "min"})
        asian_range.rename(columns={"High": "Asian_High", "Low": "Asian_Low"}, inplace=True)

        df = df.merge(asian_range, left_on="Date", right_index=True, how="left")

        df.drop(columns=["Time", "Date"], inplace=True)

        return df

    def detect_liquidity_sweeps(self, df: pd.DataFrame):
        n = len(df)

        sweep = np.zeros(n, dtype=bool)
        valid = np.zeros(n, dtype=bool)

        sweep_type = np.full(n, None, dtype=object)
        sweep_source = np.full(n, None, dtype=object)
        sweep_level = np.full(n, np.nan)
        sweep_strength = np.full(n, np.nan)
        liquidity_type = np.full(n, None, dtype=object)
        liquidity_id = np.full(n, None, dtype=object)

        highs = df["High"].values
        lows = df["Low"].values
        closes = df["Close"].values
        opens = df["Open"].values
        atr = df["ATR"].values

        eqh = df["EQH_Price"].values
        eql = df["EQL_Price"].values
        pdh = df["PDH"].values
        pdl = df["PDL"].values
        asian_high = df["Asian_High"].values
        asian_low = df["Asian_Low"].values

        bodies = np.abs(closes - opens)

        for i in range(20, n):
            curr_atr = atr[i]

            if np.isnan(curr_atr) or curr_atr <= 0:
                continue

            body = bodies[i]
            avg_body = np.mean(bodies[i - 20:i])

            if avg_body <= 0 or np.isnan(avg_body):
                continue

            bsl_sources = [
                ("PDH", pdh[i], 3, "EXTERNAL"),
                ("EQH", eqh[i - 1], 2, "INTERNAL"),
                ("ASIAN_HIGH", asian_high[i], 1, "EXTERNAL")
            ]

            ssl_sources = [
                ("PDL", pdl[i], 3, "EXTERNAL"),
                ("EQL", eql[i - 1], 2, "INTERNAL"),
                ("ASIAN_LOW", asian_low[i], 1, "EXTERNAL")
            ]

            detected = False

            for name, level, priority, liq_type in sorted(bsl_sources, key=lambda x: x[2], reverse=True):
                if np.isnan(level):
                    continue

                if highs[i] > level and closes[i] < level:
                    distance = highs[i] - level
                    strength = (distance / curr_atr) * (body / avg_body)
                    strength = min(strength, self.max_sweep_strength)

                    sweep[i] = True
                    sweep_type[i] = "Sweep_High"
                    sweep_source[i] = name
                    sweep_level[i] = level
                    sweep_strength[i] = strength
                    liquidity_type[i] = liq_type
                    liquidity_id[i] = f"LIQ_{df.index[i].strftime('%Y%m%d_%H%M')}"

                    valid[i] = (closes[i] < opens[i]) and (body > avg_body * self.displacement_multiplier) and strength >= 1.0

                    detected = True
                    break

            if detected:
                continue

            for name, level, priority, liq_type in sorted(ssl_sources, key=lambda x: x[2], reverse=True):
                if np.isnan(level):
                    continue

                if lows[i] < level and closes[i] > level:
                    distance = level - lows[i]
                    strength = (distance / curr_atr) * (body / avg_body)
                    strength = min(strength, self.max_sweep_strength)

                    sweep[i] = True
                    sweep_type[i] = "Sweep_Low"
                    sweep_source[i] = name
                    sweep_level[i] = level
                    sweep_strength[i] = strength
                    liquidity_type[i] = liq_type
                    liquidity_id[i] = f"LIQ_{df.index[i].strftime('%Y%m%d_%H%M')}"

                    valid[i] = (closes[i] > opens[i]) and (body > avg_body * self.displacement_multiplier) and strength >= 1.0
                    break

        df["Liquidity_Sweep"] = sweep
        df["Valid_Sweep"] = valid
        df["Sweep_Type"] = sweep_type
        df["Liquidity_Source"] = sweep_source
        df["Sweep_Level"] = sweep_level
        df["Sweep_Strength"] = sweep_strength
        df["Liquidity_Type"] = liquidity_type
        df["Liquidity_ID"] = liquidity_id

        return df

    def confirm_sweeps(self, df: pd.DataFrame):
        if "MSS" in df.columns:
            df["Sweep_Confirmed"] = df["Valid_Sweep"] & df["MSS"].fillna(False)
        else:
            df["Sweep_Confirmed"] = False

        if "MSS_Type" in df.columns:
            df["Confirmed_MSS_Type"] = np.where(df["Sweep_Confirmed"], df["MSS_Type"], None)
        else:
            df["Confirmed_MSS_Type"] = None

        return df

    def calculate_rank(self, df: pd.DataFrame):
        source_score = {
            "PDH": 3,
            "PDL": 3,
            "EQH": 2,
            "EQL": 2,
            "ASIAN_HIGH": 1,
            "ASIAN_LOW": 1
        }

        df["Source_Score"] = df["Liquidity_Source"].map(source_score).fillna(0)
        df["Age_Score"] = np.minimum(df["Liquidity_Age"].fillna(0) / 50, 2)

        df["Liquidity_Rank"] = (
            df["Source_Score"]
            + (df["Sweep_Strength"].fillna(0) * 1.5)
            + (df["Pool_Count"].fillna(0) * 0.5)
            + df["Age_Score"]
        )

        df["Liquidity_Rank"] = df["Liquidity_Rank"].clip(0, 10)

        return df

    def process_liquidity(self, df: pd.DataFrame):
        df = df.copy()

        if "ATR" not in df.columns:
            df["ATR"] = self.calculate_atr(df)

        df = self.detect_equal_levels(df)
        df = self.detect_time_based_liquidity(df)
        df = self.detect_liquidity_sweeps(df)
        df = self.confirm_sweeps(df)
        df = self.calculate_rank(df)

        return df