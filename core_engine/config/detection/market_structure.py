# market_structure.py
import pandas as pd
import numpy as np


class StructureState:
    def __init__(self):
        self.trend = "NEUTRAL"
        self.consecutive_bos = 0

        self.bos_count = 0
        self.choch_count = 0
        self.mss_count = 0

        self.last_swing_high = None
        self.last_swing_high_index = None
        self.last_swing_low = None
        self.last_swing_low_index = None

        self.recent_swings_high = []
        self.recent_swings_low = []

        self.last_bos_high_index = None
        self.last_bos_low_index = None

        self.protected_high = None
        self.protected_low = None

        self.last_liquidity_sweep = False
        self.sweep_type = None
        self.sweep_index = None
        self.swept_level_price = None


class MarketStructureDetector:
    def __init__(
        self,
        displacement_multiplier=1.2,
        mss_displacement_multiplier=0.90,
        bos_buffer_multiplier=0.05,
        mss_buffer_multiplier=0.02,
        max_sweep_age=16
    ):
        self.displacement_multiplier = displacement_multiplier
        self.mss_displacement_multiplier = mss_displacement_multiplier
        self.bos_buffer_multiplier = bos_buffer_multiplier
        self.mss_buffer_multiplier = mss_buffer_multiplier
        self.max_sweep_age = max_sweep_age

    def is_displacement(self, body_size, candle_range, avg_body, atr):
        if atr <= 0 or avg_body <= 0:
            return False
        return (
            body_size > avg_body * self.displacement_multiplier
            or candle_range > atr * self.displacement_multiplier
        )

    def is_mss_displacement(self, body_size, candle_range, avg_body, atr):
        if atr <= 0 or avg_body <= 0:
            return False
        return (
            body_size > avg_body * self.mss_displacement_multiplier
            or candle_range > atr * self.mss_displacement_multiplier
        )

    def detect_swings(self, df: pd.DataFrame) -> pd.DataFrame:
        n = len(df)
        highs = df["High"].values
        lows = df["Low"].values

        swing_high = np.full(n, np.nan)
        swing_low = np.full(n, np.nan)

        for i in range(2, n - 2):
            if (
                highs[i] > highs[i - 1]
                and highs[i] > highs[i - 2]
                and highs[i] > highs[i + 1]
                and highs[i] > highs[i + 2]
            ):
                swing_high[i] = highs[i]

            if (
                lows[i] < lows[i - 1]
                and lows[i] < lows[i - 2]
                and lows[i] < lows[i + 1]
                and lows[i] < lows[i + 2]
            ):
                swing_low[i] = lows[i]

        df["Swing_High"] = swing_high
        df["Swing_Low"] = swing_low
        df["Confirmed_Swing_High"] = swing_high
        df["Confirmed_Swing_Low"] = swing_low
        return df

    def _reset_sweep(self, state: StructureState):
        state.last_liquidity_sweep = False
        state.sweep_type = None
        state.sweep_index = None
        state.swept_level_price = None

    def _get_internal_high_after_sweep(self, recent_highs, sweep_index):
        candidates = [(p, idx) for p, idx in recent_highs if idx <= sweep_index and idx >= sweep_index - 12]
        if not candidates:
            return None, None
        return candidates[-1]

    def _get_internal_low_after_sweep(self, recent_lows, sweep_index):
        candidates = [(p, idx) for p, idx in recent_lows if idx <= sweep_index and idx >= sweep_index - 12]
        if not candidates:
            return None, None
        return candidates[-1]

    def process_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = self.detect_swings(df)

        state = StructureState()
        n = len(df)

        candle_bodies = (df["Close"] - df["Open"]).abs()
        df["Avg_Body"] = candle_bodies.rolling(window=20).mean()

        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean()

        bos_arr = np.zeros(n, dtype=bool)
        bos_price_arr = np.full(n, np.nan)
        bos_type_arr = np.full(n, None, dtype=object)
        bos_buffer_arr = np.full(n, np.nan)

        choch_arr = np.zeros(n, dtype=bool)
        choch_price_arr = np.full(n, np.nan)
        choch_type_arr = np.full(n, None, dtype=object)

        mss_arr = np.zeros(n, dtype=bool)
        mss_price_arr = np.full(n, np.nan)
        mss_type_arr = np.full(n, None, dtype=object)
        mss_sweep_price_arr = np.full(n, np.nan)
        mss_sweep_age_arr = np.full(n, np.nan)

        market_trend_arr = np.full(n, "NEUTRAL", dtype=object)
        structure_id_arr = np.full(n, None, dtype=object)

        strong_high_arr = np.zeros(n, dtype=bool)
        strong_low_arr = np.zeros(n, dtype=bool)
        weak_high_arr = np.zeros(n, dtype=bool)
        weak_low_arr = np.zeros(n, dtype=bool)

        protected_high_arr = np.full(n, np.nan)
        protected_low_arr = np.full(n, np.nan)

        closes = df["Close"].values
        opens = df["Open"].values
        highs = df["High"].values
        lows = df["Low"].values
        confirmed_highs = df["Confirmed_Swing_High"].values
        confirmed_lows = df["Confirmed_Swing_Low"].values
        avg_bodies = df["Avg_Body"].values
        atrs = df["ATR"].values

        for i in range(2, n):
            if not np.isnan(confirmed_highs[i - 2]):
                p_high = confirmed_highs[i - 2]
                state.last_swing_high = p_high
                state.last_swing_high_index = i - 2
                state.recent_swings_high.append((p_high, i - 2))
                if len(state.recent_swings_high) > 8:
                    state.recent_swings_high.pop(0)

            if not np.isnan(confirmed_lows[i - 2]):
                p_low = confirmed_lows[i - 2]
                state.last_swing_low = p_low
                state.last_swing_low_index = i - 2
                state.recent_swings_low.append((p_low, i - 2))
                if len(state.recent_swings_low) > 8:
                    state.recent_swings_low.pop(0)

            curr_close = closes[i]
            curr_open = opens[i]
            curr_high = highs[i]
            curr_low = lows[i]
            curr_body = abs(curr_close - curr_open)
            curr_range = curr_high - curr_low

            avg_body = avg_bodies[i] if not np.isnan(avg_bodies[i]) else 0.0
            atr_value = atrs[i] if not np.isnan(atrs[i]) else 0.0

            bos_buffer = atr_value * self.bos_buffer_multiplier
            mss_buffer = atr_value * self.mss_buffer_multiplier
            bos_buffer_arr[i] = bos_buffer

            displacement_valid = self.is_displacement(curr_body, curr_range, avg_body, atr_value)
            mss_displacement_valid = self.is_mss_displacement(curr_body, curr_range, avg_body, atr_value)

            sweep_detected = False

            for h_price, h_idx in reversed(state.recent_swings_high):
                if curr_high > h_price and curr_close < h_price:
                    state.last_liquidity_sweep = True
                    state.sweep_type = "HIGH"
                    state.sweep_index = i
                    state.swept_level_price = h_price
                    sweep_detected = True
                    break

            if not sweep_detected:
                for l_price, l_idx in reversed(state.recent_swings_low):
                    if curr_low < l_price and curr_close > l_price:
                        state.last_liquidity_sweep = True
                        state.sweep_type = "LOW"
                        state.sweep_index = i
                        state.swept_level_price = l_price
                        break

            if (
                state.last_liquidity_sweep
                and state.sweep_index is not None
                and i - state.sweep_index > self.max_sweep_age
            ):
                self._reset_sweep(state)

            mss_triggered = False
            choch_triggered = False

            sweep_valid = (
                state.last_liquidity_sweep
                and state.sweep_index is not None
                and i - state.sweep_index <= self.max_sweep_age
            )

            # =========================
            # MSS v2
            # =========================
            if sweep_valid and mss_displacement_valid:
                if state.sweep_type == "LOW":
                    trigger_high, trigger_high_idx = self._get_internal_high_after_sweep(
                        state.recent_swings_high,
                        state.sweep_index
                    )

                    if trigger_high is None:
                        trigger_high = state.last_swing_high
                        trigger_high_idx = state.last_swing_high_index

                    if (
                        trigger_high is not None
                        and curr_close > trigger_high + mss_buffer
                        and curr_close > curr_open
                    ):
                        mss_arr[i] = True
                        mss_price_arr[i] = trigger_high
                        mss_type_arr[i] = "Bullish"
                        mss_sweep_price_arr[i] = state.swept_level_price
                        mss_sweep_age_arr[i] = i - state.sweep_index

                        state.mss_count += 1
                        structure_id_arr[i] = f"MSS_{state.mss_count}"

                        state.trend = "BULLISH"
                        state.consecutive_bos = 1

                        if state.last_swing_low_index is not None:
                            state.protected_low = state.last_swing_low
                            strong_low_arr[state.last_swing_low_index] = True

                        if trigger_high_idx is not None:
                            weak_high_arr[trigger_high_idx] = True

                        state.protected_high = None
                        self._reset_sweep(state)
                        mss_triggered = True

                elif state.sweep_type == "HIGH":
                    trigger_low, trigger_low_idx = self._get_internal_low_after_sweep(
                        state.recent_swings_low,
                        state.sweep_index
                    )

                    if trigger_low is None:
                        trigger_low = state.last_swing_low
                        trigger_low_idx = state.last_swing_low_index

                    if (
                        trigger_low is not None
                        and curr_close < trigger_low - mss_buffer
                        and curr_close < curr_open
                    ):
                        mss_arr[i] = True
                        mss_price_arr[i] = trigger_low
                        mss_type_arr[i] = "Bearish"
                        mss_sweep_price_arr[i] = state.swept_level_price
                        mss_sweep_age_arr[i] = i - state.sweep_index

                        state.mss_count += 1
                        structure_id_arr[i] = f"MSS_{state.mss_count}"

                        state.trend = "BEARISH"
                        state.consecutive_bos = 1

                        if state.last_swing_high_index is not None:
                            state.protected_high = state.last_swing_high
                            strong_high_arr[state.last_swing_high_index] = True

                        if trigger_low_idx is not None:
                            weak_low_arr[trigger_low_idx] = True

                        state.protected_low = None
                        self._reset_sweep(state)
                        mss_triggered = True

            # CHoCH
            if not mss_triggered:
                if (
                    state.trend == "BULLISH"
                    and state.protected_low is not None
                    and curr_close < state.protected_low - bos_buffer
                ):
                    choch_arr[i] = True
                    choch_price_arr[i] = state.protected_low
                    choch_type_arr[i] = "Bearish"
                    state.choch_count += 1
                    structure_id_arr[i] = f"CHoCH_{state.choch_count}"
                    state.trend = "BEARISH"
                    state.consecutive_bos = 0

                    if state.last_swing_high_index is not None:
                        state.protected_high = state.last_swing_high
                        strong_high_arr[state.last_swing_high_index] = True

                    state.protected_low = None
                    self._reset_sweep(state)
                    choch_triggered = True

                elif (
                    state.trend == "BEARISH"
                    and state.protected_high is not None
                    and curr_close > state.protected_high + bos_buffer
                ):
                    choch_arr[i] = True
                    choch_price_arr[i] = state.protected_high
                    choch_type_arr[i] = "Bullish"
                    state.choch_count += 1
                    structure_id_arr[i] = f"CHoCH_{state.choch_count}"
                    state.trend = "BULLISH"
                    state.consecutive_bos = 0

                    if state.last_swing_low_index is not None:
                        state.protected_low = state.last_swing_low
                        strong_low_arr[state.last_swing_low_index] = True

                    state.protected_high = None
                    self._reset_sweep(state)
                    choch_triggered = True

            # BOS
            if not mss_triggered and not choch_triggered:
                # BOS must respect protected levels: protected level not broken (otherwise it's CHoCH)
                protected_bull_ok = state.protected_low is None or curr_close > state.protected_low
                protected_bear_ok = state.protected_high is None or curr_close < state.protected_high

                bos_condition_bull = (
                    state.last_swing_high is not None
                    and state.last_swing_high_index != state.last_bos_high_index
                    and curr_close > state.last_swing_high + bos_buffer
                    and protected_bull_ok
                    and displacement_valid
                    and curr_close > curr_open
                )

                bos_condition_bear = (
                    state.last_swing_low is not None
                    and state.last_swing_low_index != state.last_bos_low_index
                    and curr_close < state.last_swing_low - bos_buffer
                    and protected_bear_ok
                    and displacement_valid
                    and curr_close < curr_open
                )

                if state.trend in ["BULLISH", "NEUTRAL"] and bos_condition_bull:
                    bos_arr[i] = True
                    bos_price_arr[i] = state.last_swing_high
                    bos_type_arr[i] = "Bullish"
                    state.bos_count += 1
                    structure_id_arr[i] = f"BOS_{state.bos_count}"
                    state.last_bos_high_index = state.last_swing_high_index

                    state.consecutive_bos = state.consecutive_bos + 1 if state.trend == "BULLISH" else 1
                    state.trend = "BULLISH"

                    state.recent_swings_high = [
                        (p, idx)
                        for p, idx in state.recent_swings_high
                        if idx != state.last_bos_high_index
                    ]

                    if state.last_swing_low_index is not None:
                        state.protected_low = state.last_swing_low
                        strong_low_arr[state.last_swing_low_index] = True

                    if state.last_bos_high_index is not None:
                        weak_high_arr[state.last_bos_high_index] = True

                    self._reset_sweep(state)

                elif state.trend in ["BEARISH", "NEUTRAL"] and bos_condition_bear:
                    bos_arr[i] = True
                    bos_price_arr[i] = state.last_swing_low
                    bos_type_arr[i] = "Bearish"
                    state.bos_count += 1
                    structure_id_arr[i] = f"BOS_{state.bos_count}"
                    state.last_bos_low_index = state.last_swing_low_index

                    state.consecutive_bos = state.consecutive_bos + 1 if state.trend == "BEARISH" else 1
                    state.trend = "BEARISH"

                    state.recent_swings_low = [
                        (p, idx)
                        for p, idx in state.recent_swings_low
                        if idx != state.last_bos_low_index
                    ]

                    if state.last_swing_high_index is not None:
                        state.protected_high = state.last_swing_high
                        strong_high_arr[state.last_swing_high_index] = True

                    if state.last_bos_low_index is not None:
                        weak_low_arr[state.last_bos_low_index] = True

                    self._reset_sweep(state)

            if state.trend == "BULLISH":
                market_trend_arr[i] = "STRONG_BULLISH" if state.consecutive_bos > 1 else "WEAK_BULLISH"
            elif state.trend == "BEARISH":
                market_trend_arr[i] = "STRONG_BEARISH" if state.consecutive_bos > 1 else "WEAK_BEARISH"
            else:
                market_trend_arr[i] = "NEUTRAL"

            if state.protected_high is not None:
                protected_high_arr[i] = state.protected_high
            if state.protected_low is not None:
                protected_low_arr[i] = state.protected_low

        df["BOS"] = bos_arr
        df["BOS_Price"] = bos_price_arr
        df["BOS_Type"] = bos_type_arr
        df["BOS_Buffer"] = bos_buffer_arr

        df["CHoCH"] = choch_arr
        df["CHoCH_Price"] = choch_price_arr
        df["CHoCH_Type"] = choch_type_arr

        df["MSS"] = mss_arr
        df["MSS_Price"] = mss_price_arr
        df["MSS_Type"] = mss_type_arr
        df["MSS_Sweep_Price"] = mss_sweep_price_arr
        df["MSS_Sweep_Age"] = mss_sweep_age_arr

        df["Market_Trend"] = market_trend_arr
        df["Structure_ID"] = structure_id_arr

        df["Strong_High"] = strong_high_arr
        df["Strong_Low"] = strong_low_arr
        df["Weak_High"] = weak_high_arr
        df["Weak_Low"] = weak_low_arr

        df["Protected_High_Level"] = protected_high_arr
        df["Protected_Low_Level"] = protected_low_arr

        return df