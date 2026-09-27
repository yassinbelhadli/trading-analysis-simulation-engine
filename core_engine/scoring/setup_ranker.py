# setup_ranker.py
import pandas as pd
import numpy as np


class SetupRanker:
    def __init__(
        self,
        min_score=68,
        premium_score=80,
        max_daily_setups=3,
        min_daily_setups_target=1,
        cooldown_candles=12,
        max_same_direction_per_day=1,
        require_mss_or_choch=True,
        require_liquidity=True,
        require_fvg_or_ob=True,
        prefer_best_setups=True,
    ):
        self.min_score = min_score
        self.premium_score = premium_score
        self.max_daily_setups = max_daily_setups
        self.min_daily_setups_target = min_daily_setups_target
        self.cooldown_candles = cooldown_candles
        self.max_same_direction_per_day = max_same_direction_per_day

        self.require_mss_or_choch = require_mss_or_choch
        self.require_liquidity = require_liquidity
        self.require_fvg_or_ob = require_fvg_or_ob
        self.prefer_best_setups = prefer_best_setups

    def _get_session(self, timestamp):
        hour = timestamp.hour
        if 7 <= hour < 12:
            return "LONDON"
        if 13 <= hour < 17:
            return "NEWYORK"
        return "OTHER"

    def _safe_str(self, row, col, default=""):
        try:
            val = row.get(col, default)
            if pd.isna(val) or val is None:
                return default
            return str(val)
        except Exception:
            return default

    def _safe_bool(self, row, col):
        try:
            return bool(row.get(col, False))
        except Exception:
            return False

    def _safe_float(self, row, col, default=0.0):
        try:
            value = row.get(col, default)
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default

    def _structure_ok(self, row):
        if not self.require_mss_or_choch:
            return True

        return (
            self._safe_bool(row, "MSS")
            or self._safe_bool(row, "CHoCH")
            or self._safe_bool(row, "BOS")
        )

    def _liquidity_ok(self, row):
        if not self.require_liquidity:
            return True

        return (
            self._safe_bool(row, "Valid_Sweep")
            or self._safe_bool(row, "Liquidity_Sweep")
            or self._safe_float(row, "Liquidity_Rank", 0) >= 2
        )

    def _imbalance_ok(self, row, direction):
        if not self.require_fvg_or_ob:
            return True

        if direction == "BUY":
            return (
                self._safe_str(row, "Active_OB_Type") == "Bullish"
                or self._safe_str(row, "Active_FVG_Type") == "Bullish"
                or self._safe_bool(row, "Bullish_FVG")
                or self._safe_bool(row, "Bullish_OB")
                or self._safe_bool(row, "Bullish_VI")
                or self._safe_bool(row, "Bullish_LV")
            )

        if direction == "SELL":
            return (
                self._safe_str(row, "Active_OB_Type") == "Bearish"
                or self._safe_str(row, "Active_FVG_Type") == "Bearish"
                or self._safe_bool(row, "Bearish_FVG")
                or self._safe_bool(row, "Bearish_OB")
                or self._safe_bool(row, "Bearish_VI")
                or self._safe_bool(row, "Bearish_LV")
            )

        return False

    def _pd_ok(self, row, direction):
        if direction == "BUY":
            return (
                self._safe_bool(row, "PD_Valid_Buy")
                or self._safe_bool(row, "Discount_Zone")
                or self._safe_str(row, "PD_State") in ["DISCOUNT", "EQUILIBRIUM"]
            )

        if direction == "SELL":
            return (
                self._safe_bool(row, "PD_Valid_Sell")
                or self._safe_bool(row, "Premium_Zone")
                or self._safe_str(row, "PD_State") in ["PREMIUM", "EQUILIBRIUM"]
            )

        return False

    def _candle_ok(self, row, direction):
        if direction == "BUY":
            return (
                self._safe_bool(row, "Candle_Valid_Buy")
                or self._safe_str(row, "Candle_Direction") == "Bullish"
                or "Bullish" in self._safe_str(row, "Candle_Pattern")
            )

        if direction == "SELL":
            return (
                self._safe_bool(row, "Candle_Valid_Sell")
                or self._safe_str(row, "Candle_Direction") == "Bearish"
                or "Bearish" in self._safe_str(row, "Candle_Pattern")
            )

        return False

    def _session_bonus(self, session):
        if session == "NEWYORK":
            return 2.0
        if session == "LONDON":
            return 1.0
        return 0.0

    def _rank_label(self, score):
        if score >= 90:
            return "ELITE_A_PLUS"
        if score >= self.premium_score:
            return "A_PLUS"
        if score >= self.min_score:
            return "A"
        if score >= 55:
            return "B"
        return "IGNORE"

    def _base_pass(self, row):
        score = self._safe_float(row, "Setup_Score", 0)
        direction = row.get("Trade_Direction", None)
        session = row.get("Setup_Session", None)

        if direction not in ["BUY", "SELL"]:
            return False, "NO_DIRECTION"

        if score < self.min_score:
            return False, "LOW_SCORE"

        if session not in ["LONDON", "NEWYORK"]:
            return False, "BAD_SESSION"

        if not self._structure_ok(row):
            return False, "NO_STRUCTURE_CONFIRMATION"

        if not self._liquidity_ok(row):
            return False, "NO_LIQUIDITY"

        if not self._imbalance_ok(row, direction):
            return False, "NO_ACTIVE_OB_OR_FVG"

        if not self._pd_ok(row, direction):
            return False, "BAD_PREMIUM_DISCOUNT"

        if not self._candle_ok(row, direction):
            return False, "NO_CANDLE_CONFIRMATION"

        return True, "BASE_PASS"

    def _candidate_priority_score(self, row):
        score = self._safe_float(row, "Setup_Score", 0)
        confidence = self._safe_float(row, "Confidence_Score", 0)
        session = row.get("Setup_Session", None)

        priority = score
        priority += confidence * 0.25
        priority += self._session_bonus(session)

        if self._safe_bool(row, "Valid_Sweep"):
            priority += 3.0

        if self._safe_bool(row, "MSS"):
            priority += 2.0

        if self._safe_bool(row, "CHoCH"):
            priority += 1.5

        if self._safe_str(row, "Active_OB_Type") in ["Bullish", "Bearish"]:
            priority += 1.0

        if self._safe_str(row, "Active_FVG_Type") in ["Bullish", "Bearish"]:
            priority += 1.0

        return round(priority, 5)

    def _approve_best_per_day(self, df: pd.DataFrame) -> pd.DataFrame:
        valid_indices = []

        grouped = df[df["Setup_Reject_Reason"] == "BASE_PASS"].groupby("Setup_Date")

        for date, day_df in grouped:
            day_df = day_df.copy()
            day_df["Candidate_Priority_Score"] = day_df.apply(
                self._candidate_priority_score,
                axis=1
            )

            day_df = day_df.sort_values(
                ["Candidate_Priority_Score", "Setup_Score"],
                ascending=False
            )

            selected = []
            direction_count = {"BUY": 0, "SELL": 0}

            for idx, row in day_df.iterrows():
                direction = row.get("Trade_Direction")

                if len(selected) >= self.max_daily_setups:
                    break

                if direction_count.get(direction, 0) >= self.max_same_direction_per_day:
                    continue

                if selected:
                    last_idx_position = df.index.get_loc(selected[-1])
                    current_idx_position = df.index.get_loc(idx)
                    if abs(current_idx_position - last_idx_position) < self.cooldown_candles:
                        continue

                selected.append(idx)
                direction_count[direction] += 1

            valid_indices.extend(selected)

        for idx in valid_indices:
            direction = df.at[idx, "Trade_Direction"]
            df.at[idx, "Setup_Approved"] = True
            df.at[idx, "Setup_Reject_Reason"] = "APPROVED"
            df.at[idx, "Setup_ID"] = f"SETUP_{idx.strftime('%Y%m%d_%H%M')}_{direction}"

        rejected_mask = (
            (df["Setup_Reject_Reason"] == "BASE_PASS")
            & (df["Setup_Approved"] == False)
        )
        df.loc[rejected_mask, "Setup_Reject_Reason"] = "NOT_TOP_DAILY_SETUP"

        return df

    def _approve_sequential(self, df: pd.DataFrame) -> pd.DataFrame:
        daily_count = {}
        daily_buy_count = {}
        daily_sell_count = {}
        last_setup_index = -999999

        for i in range(len(df)):
            row = df.iloc[i]
            idx = df.index[i]

            if row["Setup_Reject_Reason"] != "BASE_PASS":
                continue

            date = row["Setup_Date"]
            direction = row.get("Trade_Direction", None)

            if date not in daily_count:
                daily_count[date] = 0
                daily_buy_count[date] = 0
                daily_sell_count[date] = 0

            if daily_count[date] >= self.max_daily_setups:
                df.at[idx, "Setup_Reject_Reason"] = "DAILY_LIMIT_REACHED"
                continue

            if i - last_setup_index < self.cooldown_candles:
                df.at[idx, "Setup_Reject_Reason"] = "COOLDOWN"
                continue

            if direction == "BUY" and daily_buy_count[date] >= self.max_same_direction_per_day:
                df.at[idx, "Setup_Reject_Reason"] = "TOO_MANY_BUYS"
                continue

            if direction == "SELL" and daily_sell_count[date] >= self.max_same_direction_per_day:
                df.at[idx, "Setup_Reject_Reason"] = "TOO_MANY_SELLS"
                continue

            df.at[idx, "Setup_Approved"] = True
            df.at[idx, "Setup_Reject_Reason"] = "APPROVED"
            df.at[idx, "Setup_ID"] = f"SETUP_{idx.strftime('%Y%m%d_%H%M')}_{direction}"

            daily_count[date] += 1
            last_setup_index = i

            if direction == "BUY":
                daily_buy_count[date] += 1
            elif direction == "SELL":
                daily_sell_count[date] += 1

        return df

    def process_rankings(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be DatetimeIndex")

        df["Setup_Date"] = df.index.date
        df["Setup_Session"] = df.index.map(self._get_session)

        df["Setup_Approved"] = False
        df["Setup_Rank"] = "IGNORE"
        df["Setup_Reject_Reason"] = None
        df["Setup_Final_Score"] = 0.0
        df["Setup_ID"] = None
        df["Candidate_Priority_Score"] = 0.0

        for i in range(len(df)):
            row = df.iloc[i]
            idx = df.index[i]

            score = self._safe_float(row, "Setup_Score", 0)

            df.at[idx, "Setup_Final_Score"] = min(score, 100)
            df.at[idx, "Setup_Rank"] = self._rank_label(score)

            passed, reason = self._base_pass(row)
            df.at[idx, "Setup_Reject_Reason"] = reason

            if passed:
                df.at[idx, "Candidate_Priority_Score"] = self._candidate_priority_score(row)

        if self.prefer_best_setups:
            df = self._approve_best_per_day(df)
        else:
            df = self._approve_sequential(df)

        df["Daily_Approved_Setups"] = df.groupby("Setup_Date")["Setup_Approved"].transform("sum")

        df["Daily_Setup_Target_OK"] = (
            (df["Daily_Approved_Setups"] >= self.min_daily_setups_target)
            & (df["Daily_Approved_Setups"] <= self.max_daily_setups)
        )

        return df

    def get_approved_setups(self, df: pd.DataFrame):
        if "Setup_Approved" not in df.columns:
            return pd.DataFrame()
        return df[df["Setup_Approved"] == True].copy()

    def get_daily_summary(self, df: pd.DataFrame):
        if "Setup_Date" not in df.columns:
            return {}

        return df.groupby("Setup_Date").agg(
            Approved_Setups=("Setup_Approved", "sum"),
            Avg_Score=("Setup_Final_Score", "mean"),
            Max_Score=("Setup_Final_Score", "max"),
            Avg_Priority=("Candidate_Priority_Score", "mean"),
            Max_Priority=("Candidate_Priority_Score", "max"),
        )