# entry_manager.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import pandas as pd
import numpy as np

from core_engine.risk.account_profile import AccountProfile
from core_engine.risk.lot_calculator import LotCalculator
from core_engine.risk.symbol_validator import SymbolValidator
from core_engine.risk.daily_loss_guard import DailyLossGuard
from core_engine.risk.max_loss_guard import MaxLossGuard
from core_engine.risk.drawdown_protection import DrawdownProtection
from core_engine.risk.funded_risk import FundedRiskManager
from core_engine.filters.trade_quality_filter import TradeQualityFilter
from core_engine.config.market_profiles import get_market_profile
from core_engine.config.trading_modes import (
    get_trading_mode,
    calculate_mode_risk,
)

from news_engine.calendar import EconomicCalendar
from news_engine.news_filter import NewsFilter
from news_engine.fundamental_state import FundamentalState


@dataclass
class EntryDecision:
    can_execute: bool
    reason: str
    symbol: str
    normalized_symbol: str
    market: Optional[str]
    direction: Optional[str]
    entry_type: Optional[str]
    entry_price: float
    stop_loss: float
    take_profit: float
    rr: float
    lot_size: float
    setup_id: Optional[str]
    confidence_score: float
    setup_score: float
    risk_amount: float
    actual_risk_amount: float
    actual_risk_percent: float
    session_name: Optional[str]
    killzone: Optional[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EntryManager:
    def __init__(
        self,
        min_confidence=55,
        min_rr=1.5,
        default_entry_mode="SMART",
        sl_atr_buffer_mult=0.20,
        max_sl_atr_mult=3.0,
        require_zone_entry=True,
    ):
        self.min_confidence = min_confidence
        self.min_rr = min_rr
        self.default_entry_mode = default_entry_mode
        self.sl_atr_buffer_mult = sl_atr_buffer_mult
        self.max_sl_atr_mult = max_sl_atr_mult
        self.require_zone_entry = require_zone_entry

        self.lot_calculator = LotCalculator()
        self.symbol_validator = SymbolValidator()
        self.daily_guard = DailyLossGuard()
        self.max_loss_guard = MaxLossGuard()
        self.dd_protection = DrawdownProtection()
        self.funded_manager = FundedRiskManager()

        self.fundamental_state = FundamentalState()

        self.news_calendar = EconomicCalendar()
        self.news_filter = NewsFilter(
            block_before_minutes=60,
            block_after_minutes=30,
            block_high_only=True,
        )

        root = Path(__file__).resolve().parents[2]
        news_file = root / "data" / "processed" / "news_cache.csv"

        if news_file.exists():
            self.news_calendar.load_from_csv(news_file)
            print("ENTRY MANAGER NEWS LOADED:", len(self.news_calendar.get_events()))
        else:
            print("NEWS FILE NOT FOUND:", news_file)

    def _build_trade_quality_filter(
        self,
        normalized_symbol: str,
        min_setup_score: float = 65.0,
    ) -> TradeQualityFilter:
        profile_cfg = get_market_profile(normalized_symbol)

        return TradeQualityFilter(
            min_setup_score=min_setup_score,
            sell_fvg_min_score=profile_cfg["sell_fvg_min_score"],
            sell_ob_min_score=profile_cfg["sell_ob_min_score"],
            buy_fvg_min_score=profile_cfg["buy_fvg_min_score"],
            buy_ob_min_score=profile_cfg["buy_ob_min_score"],
            max_sl_distance_gold=45.0,
            max_sl_distance_nasdaq=180.0,
            max_sl_distance_btc=800.0,
            reject_raw_lot_below_min=True,
            min_raw_lot_size=0.01,
            reject_strong_zone_conflict=False,
        )

    def build_entry_decision(
        self,
        row: pd.Series,
        profile: AccountProfile,
        current_equity: float,
        daily_start_equity: float,
        start_balance: Optional[float] = None,
        peak_equity: Optional[float] = None,
        symbol: Optional[str] = None,
        entry_mode: Optional[str] = None,
        trading_mode: str = "BALANCED",
    ) -> EntryDecision:

        entry_mode = (entry_mode or self.default_entry_mode).upper()
        mode_name = trading_mode or getattr(profile, "trading_mode", "CONSERVATIVE")
        mode_config = get_trading_mode(mode_name)

        symbol = symbol or profile.primary_symbol or profile.symbol
        normalized_symbol = self.symbol_validator.normalize_symbol(symbol)
        market = self.symbol_validator.classify_symbol_market(symbol)

        base_metadata = {
            "entry_mode": entry_mode,
            "trading_mode": mode_config.to_dict(),
            "profile_type": profile.account_type,
            "profile_allowed_symbols": profile.allowed_symbols,
            "profile_enabled_markets": profile.enabled_markets,
            "require_zone_entry": self.require_zone_entry,
            "active_ob_type": row.get("Active_OB_Type", None),
            "active_fvg_type": row.get("Active_FVG_Type", None),
            "market_profile": get_market_profile(normalized_symbol),
        }

        if normalized_symbol not in ["XAUUSD", "NAS100", "BTCUSD"]:
            return self._reject("UNSUPPORTED_SYMBOL", symbol, normalized_symbol, market, row, base_metadata)

        if profile.allowed_symbols and not self.symbol_validator.is_symbol_allowed(symbol, profile.allowed_symbols):
            return self._reject("SYMBOL_NOT_ALLOWED_FOR_CLIENT", symbol, normalized_symbol, market, row, base_metadata)

        direction = row.get("Trade_Direction", None)

        if direction not in ["BUY", "SELL"]:
            return self._reject("NO_TRADE_DIRECTION", symbol, normalized_symbol, market, row, base_metadata)

        if not self._directional_zone_ok(row, direction):
            return self._reject("ZONE_DIRECTION_MISMATCH", symbol, normalized_symbol, market, row, base_metadata)

        if not bool(row.get("Setup_Approved", False)):
            return self._reject("SETUP_NOT_APPROVED", symbol, normalized_symbol, market, row, base_metadata)

        if not bool(row.get("Confidence_Approved", False)):
            return self._reject("CONFIDENCE_NOT_APPROVED", symbol, normalized_symbol, market, row, base_metadata)

        confidence = self._safe_float(row.get("Confidence_Score", 0))
        setup_score = self._safe_float(row.get("Setup_Score", 0))

        dynamic_risk = calculate_mode_risk(
            mode_name,
            setup_score,
        )

        base_metadata["dynamic_risk_percent"] = dynamic_risk

        if confidence < mode_config.min_confidence_score:
            return self._reject("MODE_CONFIDENCE_TOO_LOW", symbol, normalized_symbol, market, row, base_metadata)

        if setup_score < mode_config.min_setup_score:
            return self._reject("MODE_SETUP_SCORE_TOO_LOW", symbol, normalized_symbol, market, row, base_metadata)

        session_ok = (
            bool(row.get("Session_Trade_Allowed", False))
            or bool(row.get("London_Trade_Allowed", False))
            or bool(row.get("NewYork_Trade_Allowed", False))
        )

        if not session_ok:
            return self._reject("SESSION_NOT_ALLOWED", symbol, normalized_symbol, market, row, base_metadata)

        if "Weekend_Trade_Allowed" in row and not bool(row.get("Weekend_Trade_Allowed", True)):
            return self._reject(
                str(row.get("Weekend_Block_Reason", "WEEKEND_BLOCK")),
                symbol,
                normalized_symbol,
                market,
                row,
                base_metadata,
            )

        news_result = self._check_news_filter(
            symbol=normalized_symbol,
            current_time=row.name,
        )

        base_metadata["news_filter"] = news_result.to_dict()

        if not news_result.allowed:
            return self._reject(
                f"NEWS_{news_result.reason}",
                symbol,
                normalized_symbol,
                market,
                row,
                base_metadata,
            )

        fundamental_result = self._check_fundamental_bias(
            symbol=normalized_symbol,
            direction=direction,
        )

        base_metadata["fundamental_state"] = fundamental_result

        if not fundamental_result["allowed"]:
            return self._reject(
                fundamental_result["reason"],
                symbol,
                normalized_symbol,
                market,
                row,
                base_metadata,
            )

        entry_price, entry_source = self._select_entry_price(row, direction, entry_mode)
        stop_loss, sl_source = self._select_stop_loss(row, direction, entry_source)

        base_metadata["entry_source"] = entry_source
        base_metadata["sl_source"] = sl_source

        if self.require_zone_entry and "FALLBACK" in entry_source:
            return self._reject(
                "NO_VALID_DIRECTIONAL_OB_OR_FVG_ENTRY_ZONE",
                symbol,
                normalized_symbol,
                market,
                row,
                base_metadata,
            )

        if entry_price <= 0 or stop_loss <= 0:
            return self._reject("INVALID_ENTRY_OR_SL", symbol, normalized_symbol, market, row, base_metadata)

        if direction == "BUY" and stop_loss >= entry_price:
            return self._reject("BUY_SL_INVALID", symbol, normalized_symbol, market, row, base_metadata)

        if direction == "SELL" and stop_loss <= entry_price:
            return self._reject("SELL_SL_INVALID", symbol, normalized_symbol, market, row, base_metadata)

        rr = self._safe_float(getattr(profile, "preferred_rr", 2.0), 2.0)

        if rr < mode_config.min_rr:
            return self._reject("MODE_RR_TOO_LOW", symbol, normalized_symbol, market, row, base_metadata)

        profile_for_trade = AccountProfile.from_dict(profile.to_dict())
        profile_for_trade.risk_per_trade = dynamic_risk

        lot_result = self.lot_calculator.calculate_lot(
            profile=profile_for_trade,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            direction=direction,
            rr=rr,
        )

        if not lot_result.valid:
            return self._reject(
                f"LOT_INVALID_{lot_result.reason}",
                symbol,
                normalized_symbol,
                market,
                row,
                {**base_metadata, "lot_result": lot_result.to_dict()},
            )

        trade_quality_filter = self._build_trade_quality_filter(
            normalized_symbol,
            min_setup_score=mode_config.min_setup_score,
        )

        quality_result = trade_quality_filter.evaluate(
            row=row,
            symbol=normalized_symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            entry_source=entry_source,
            lot_result=lot_result,
        )

        base_metadata["trade_quality"] = quality_result.to_dict()

        if not quality_result.allowed:
            return self._reject(
                f"TRADE_QUALITY_{quality_result.reason}",
                symbol,
                normalized_symbol,
                market,
                row,
                base_metadata,
            )

        daily_result = self.daily_guard.evaluate(
            profile=profile,
            current_equity=current_equity,
            daily_start_equity=daily_start_equity,
            planned_risk_amount=lot_result.actual_risk_amount,
        )

        if not daily_result.allowed:
            return self._reject(
                f"DAILY_GUARD_{daily_result.state}",
                symbol,
                normalized_symbol,
                market,
                row,
                {**base_metadata, "daily_guard": daily_result.to_dict()},
            )

        max_loss_result = self.max_loss_guard.evaluate(
            profile=profile,
            current_equity=current_equity,
            start_balance=start_balance or profile.balance,
            planned_risk_amount=lot_result.actual_risk_amount,
        )

        if not max_loss_result.allowed:
            return self._reject(
                f"MAX_LOSS_GUARD_{max_loss_result.state}",
                symbol,
                normalized_symbol,
                market,
                row,
                {**base_metadata, "max_loss_guard": max_loss_result.to_dict()},
            )

        dd_result = self.dd_protection.evaluate(
            profile=profile,
            current_equity=current_equity,
            start_balance=start_balance or profile.balance,
            peak_equity=peak_equity,
        )

        if not dd_result.allowed:
            return self._reject(
                f"DRAWDOWN_{dd_result.state}",
                symbol,
                normalized_symbol,
                market,
                row,
                {**base_metadata, "drawdown": dd_result.to_dict()},
            )

        funded_result = self.funded_manager.evaluate(
            profile=profile,
            current_equity=current_equity,
            daily_start_equity=daily_start_equity,
            start_balance=start_balance or profile.balance,
            open_trade_risk_amount=lot_result.actual_risk_amount,
        )

        if not funded_result.allowed:
            return self._reject(
                f"FUNDED_RISK_{funded_result.risk_state}",
                symbol,
                normalized_symbol,
                market,
                row,
                {**base_metadata, "funded_risk": funded_result.to_dict()},
            )

        return EntryDecision(
            can_execute=True,
            reason="TRADE_READY",
            symbol=symbol,
            normalized_symbol=normalized_symbol,
            market=market,
            direction=direction,
            entry_type=entry_mode,
            entry_price=round(entry_price, 5),
            stop_loss=round(stop_loss, 5),
            take_profit=lot_result.take_profit_price,
            rr=rr,
            lot_size=lot_result.lot_size,
            setup_id=row.get("Setup_ID", None),
            confidence_score=confidence,
            setup_score=setup_score,
            risk_amount=lot_result.risk_amount,
            actual_risk_amount=lot_result.actual_risk_amount,
            actual_risk_percent=lot_result.actual_risk_percent,
            session_name=row.get("Session_Name", None),
            killzone=row.get("Killzone", None),
            metadata={
                **base_metadata,
                "lot_result": lot_result.to_dict(),
                "daily_guard": daily_result.to_dict(),
                "max_loss_guard": max_loss_result.to_dict(),
                "drawdown": dd_result.to_dict(),
                "funded_risk": funded_result.to_dict(),
            },
        )

    def _check_fundamental_bias(self, symbol: str, direction: str) -> Dict[str, Any]:
        usd_state = self.fundamental_state.get_currency("USD")

        if not usd_state:
            return {
                "allowed": True,
                "reason": "NO_FUNDAMENTAL_STATE",
                "bias": "NEUTRAL",
            }

        bias = usd_state.get("bias", "NEUTRAL")
        strength = self._safe_float(usd_state.get("strength", 0))
        confidence = self._safe_float(usd_state.get("confidence", 0))

        result = {
            "allowed": True,
            "reason": "FUNDAMENTAL_OK",
            "bias": bias,
            "strength": strength,
            "confidence": confidence,
            "last_event": usd_state.get("last_event", ""),
            "impact": usd_state.get("impact", ""),
            "source": usd_state.get("source", ""),
            "updated_at": usd_state.get("updated_at", ""),
        }

        if strength < 50 or confidence < 50:
            result["reason"] = "FUNDAMENTAL_WEAK_OR_NEUTRAL"
            return result

        symbol = symbol.upper()

        if symbol in ["XAUUSD", "NAS100", "BTCUSD"]:
            if bias == "BULLISH" and direction == "BUY":
                result["allowed"] = False
                result["reason"] = "FUNDAMENTAL_CONFLICT_USD_BULLISH_SELL_ONLY"
                return result

            if bias == "BEARISH" and direction == "SELL":
                result["allowed"] = False
                result["reason"] = "FUNDAMENTAL_CONFLICT_USD_BEARISH_BUY_ONLY"
                return result

        return result

    def _directional_zone_ok(self, row: pd.Series, direction: str) -> bool:
        active_ob_type = row.get("Active_OB_Type", None)
        active_fvg_type = row.get("Active_FVG_Type", None)

        if not self.require_zone_entry:
            return True

        if direction == "BUY":
            return active_ob_type == "Bullish" or active_fvg_type == "Bullish"

        if direction == "SELL":
            return active_ob_type == "Bearish" or active_fvg_type == "Bearish"

        return False

    def _select_entry_price(self, row: pd.Series, direction: str, entry_mode: str) -> Tuple[float, str]:
        close = self._safe_float(row.get("Close", 0))
        entry_mode = entry_mode.upper()

        fvg_mid = self._safe_float(row.get("Active_FVG_Midpoint", np.nan), np.nan)
        ob_mid = self._safe_float(row.get("Active_OB_Midpoint", np.nan), np.nan)

        fvg_upper = self._safe_float(row.get("Active_FVG_Upper", np.nan), np.nan)
        fvg_lower = self._safe_float(row.get("Active_FVG_Lower", np.nan), np.nan)

        ob_upper = self._safe_float(row.get("Active_OB_Upper", np.nan), np.nan)
        ob_lower = self._safe_float(row.get("Active_OB_Lower", np.nan), np.nan)

        active_fvg_type = row.get("Active_FVG_Type", None)
        active_ob_type = row.get("Active_OB_Type", None)

        if pd.isna(fvg_mid) and pd.notna(fvg_upper) and pd.notna(fvg_lower):
            fvg_mid = (fvg_upper + fvg_lower) / 2

        if pd.isna(ob_mid) and pd.notna(ob_upper) and pd.notna(ob_lower):
            ob_mid = (ob_upper + ob_lower) / 2

        if entry_mode == "MARKET":
            return close, "CLOSE_MARKET"

        if entry_mode == "FVG_MIDPOINT":
            if direction == "BUY" and pd.notna(fvg_mid) and active_fvg_type == "Bullish":
                return float(fvg_mid), "ACTIVE_FVG_MIDPOINT_BULLISH"
            if direction == "SELL" and pd.notna(fvg_mid) and active_fvg_type == "Bearish":
                return float(fvg_mid), "ACTIVE_FVG_MIDPOINT_BEARISH"
            return close, "CLOSE_FALLBACK_NO_DIRECTIONAL_ACTIVE_FVG"

        if entry_mode == "OB_MIDPOINT":
            if direction == "BUY" and pd.notna(ob_mid) and active_ob_type == "Bullish":
                return float(ob_mid), "ACTIVE_OB_MIDPOINT_BULLISH"
            if direction == "SELL" and pd.notna(ob_mid) and active_ob_type == "Bearish":
                return float(ob_mid), "ACTIVE_OB_MIDPOINT_BEARISH"
            return close, "CLOSE_FALLBACK_NO_DIRECTIONAL_ACTIVE_OB"

        if entry_mode == "SMART":
            if direction == "BUY":
                if pd.notna(fvg_mid) and active_fvg_type == "Bullish":
                    return float(fvg_mid), "SMART_ACTIVE_FVG_BULLISH"
                if pd.notna(ob_mid) and active_ob_type == "Bullish":
                    return float(ob_mid), "SMART_ACTIVE_OB_BULLISH"

            if direction == "SELL":
                if pd.notna(fvg_mid) and active_fvg_type == "Bearish":
                    return float(fvg_mid), "SMART_ACTIVE_FVG_BEARISH"
                if pd.notna(ob_mid) and active_ob_type == "Bearish":
                    return float(ob_mid), "SMART_ACTIVE_OB_BEARISH"

            return close, "SMART_CLOSE_FALLBACK"

        return close, "UNKNOWN_MODE_CLOSE_FALLBACK"

    def _select_stop_loss(
        self,
        row: pd.Series,
        direction: str,
        entry_source: Optional[str] = None
    ) -> Tuple[float, str]:

        atr = self._safe_float(row.get("ATR", 0), 0)
        buffer = atr * self.sl_atr_buffer_mult if atr > 0 else 0

        if direction == "BUY":
            candidates = {}

            if entry_source and "OB" in entry_source:
                candidates["Active_OB_Lower"] = row.get("Active_OB_Lower", np.nan)
            elif entry_source and "FVG" in entry_source:
                candidates["Active_FVG_Lower"] = row.get("Active_FVG_Lower", np.nan)
            else:
                candidates["Active_OB_Lower"] = row.get("Active_OB_Lower", np.nan)
                candidates["Active_FVG_Lower"] = row.get("Active_FVG_Lower", np.nan)

            candidates.update({
                "Support_Level": row.get("Support_Level", np.nan),
                "Sweep_Level": row.get("Sweep_Level", np.nan),
                "Low": row.get("Low", np.nan),
            })

            valid = {
                k: self._safe_float(v, np.nan)
                for k, v in candidates.items()
                if pd.notna(v)
            }

            if not valid:
                return 0.0, "NO_SL_CANDIDATE"

            source = min(valid, key=valid.get)
            return float(valid[source] - buffer), source

        if direction == "SELL":
            candidates = {}

            if entry_source and "OB" in entry_source:
                candidates["Active_OB_Upper"] = row.get("Active_OB_Upper", np.nan)
            elif entry_source and "FVG" in entry_source:
                candidates["Active_FVG_Upper"] = row.get("Active_FVG_Upper", np.nan)
            else:
                candidates["Active_OB_Upper"] = row.get("Active_OB_Upper", np.nan)
                candidates["Active_FVG_Upper"] = row.get("Active_FVG_Upper", np.nan)

            candidates.update({
                "Resistance_Level": row.get("Resistance_Level", np.nan),
                "Sweep_Level": row.get("Sweep_Level", np.nan),
                "High": row.get("High", np.nan),
            })

            valid = {
                k: self._safe_float(v, np.nan)
                for k, v in candidates.items()
                if pd.notna(v)
            }

            if not valid:
                return 0.0, "NO_SL_CANDIDATE"

            source = max(valid, key=valid.get)
            return float(valid[source] + buffer), source

        return 0.0, "INVALID_DIRECTION"

    def _check_news_filter(self, symbol: str, current_time):
        if current_time is None:
            class Dummy:
                allowed = True
                reason = "NO_TIME"

                def to_dict(self):
                    return {"allowed": True, "reason": "NO_TIME"}

            return Dummy()

        if len(self.news_calendar.get_events()) == 0:
            class Dummy:
                allowed = True
                reason = "NO_NEWS_LOADED"

                def to_dict(self):
                    return {"allowed": True, "reason": "NO_NEWS_LOADED"}

            return Dummy()

        return self.news_filter.evaluate(
            symbol=symbol,
            current_time=current_time,
            calendar=self.news_calendar,
        )

    def _reject(
        self,
        reason,
        symbol,
        normalized_symbol,
        market,
        row,
        metadata=None
    ) -> EntryDecision:
        return EntryDecision(
            can_execute=False,
            reason=reason,
            symbol=symbol,
            normalized_symbol=normalized_symbol,
            market=market,
            direction=row.get("Trade_Direction", None),
            entry_type=None,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            rr=0.0,
            lot_size=0.0,
            setup_id=row.get("Setup_ID", None),
            confidence_score=self._safe_float(row.get("Confidence_Score", 0)),
            setup_score=self._safe_float(row.get("Setup_Score", 0)),
            risk_amount=0.0,
            actual_risk_amount=0.0,
            actual_risk_percent=0.0,
            session_name=row.get("Session_Name", None),
            killzone=row.get("Killzone", None),
            metadata=metadata or {},
        )

    def _safe_float(self, value, default=0.0) -> float:
        try:
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default