from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from database.db import async_session_factory
from database.models import TradingAccount, AuditLog, RiskProfile
from database.repositories import AccountRepository, LicenseRepository
from core_engine.engine_manager import engine_manager
from core_engine.mt_runtime import MTRuntime, MTSymbolInfo
from core_engine.risk.daily_loss_guard import DailyLossGuard
from core_engine.risk.max_loss_guard import MaxLossGuard
from core_engine.risk.account_profile import AccountProfile, AccountProfileBuilder
from core_engine.events.event_types import EventType
from core_engine.events.event_bus import event_bus
from core_engine.config.trading_modes import get_trading_mode
from config.settings import ALLOW_REAL_TRADING, DEMO_ONLY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Guard Result
# ---------------------------------------------------------------------------


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ExecutionGuard
# ---------------------------------------------------------------------------


class ExecutionGuard:
    def __init__(self, runtime: MTRuntime, account_id: str, user_id: str):
        self.runtime = runtime
        self.account_id = account_id
        self.user_id = user_id
        self._warnings: List[str] = []

    def _fail(self, reason: str) -> GuardResult:
        return GuardResult(allowed=False, reason=reason, warnings=self._warnings)

    def _pass(self) -> GuardResult:
        return GuardResult(allowed=True, reason="", warnings=self._warnings)

    # ------------------------------------------------------------------
    # Master check — runs all guards in order
    # ------------------------------------------------------------------

    async def can_execute(self, account: Optional[TradingAccount] = None,
                          symbol: str = "", direction: str = "",
                          trade_mode: str = "CONSERVATIVE") -> GuardResult:
        self._warnings = []

        account = account or await self._load_account()
        if account is None:
            result = self._fail("Account not found")
            await self._log_block("account", "Account not found", symbol, direction)
            return result

        for check_name, check in (("runtime", self.validate_runtime),
                                  ("engine", self._validate_engine)):
            result = check()
            if not result.allowed:
                await self._log_block(check_name, result.reason, symbol, direction)
                return result

        if account is not None:
            for check_name, check in (("license", self._validate_license),
                                      ("risk", self._validate_risk)):
                result = await check(account)
                if not result.allowed:
                    await self._log_block(check_name, result.reason, symbol, direction)
                    return result

            # --- Risk-based checks using stored baselines ---
            for check_name in ("daily_loss", "max_loss"):
                result = await self._validate_risk_guard(check_name, account)
                if not result.allowed:
                    await self._log_block(check_name, result.reason, symbol, direction)
                    return result

        mode_config = get_trading_mode(trade_mode)

        # --- Market-level checks (only when symbol is provided) ---
        if symbol:
            result = await self.validate_symbol(symbol)
            if not result.allowed:
                await self._log_block("symbol", result.reason, symbol, direction)
                return result

            result = await self.validate_market_open(symbol)
            if not result.allowed:
                await self._log_block("market_open", result.reason, symbol, direction)
                return result

            result = await self.validate_spread(symbol)
            if not result.allowed:
                await self._log_block("spread", result.reason, symbol, direction)
                return result

            result = await self.validate_news(symbol)
            if not result.allowed:
                await self._log_block("news", result.reason, symbol, direction)
                return result

            result = await self.validate_calendar_news(symbol)
            if not result.allowed:
                await self._log_block("calendar_news", result.reason, symbol, direction)
                return result

            result = await self.validate_session(symbol, mode_config.allowed_sessions)
            if not result.allowed:
                await self._log_block("session", result.reason, symbol, direction)
                return result

            if direction:
                result = await self.validate_duplicate_trade(symbol, direction)
                if not result.allowed:
                    await self._log_block("duplicate", result.reason, symbol, direction)
                    return result

            result = await self.validate_daily_limit(
                symbol,
                max_trades_per_symbol=mode_config.max_trades_per_symbol_per_day,
                max_trades_total=mode_config.max_trades_per_day,
            )
            if not result.allowed:
                await self._log_block("daily_limit", result.reason, symbol, direction)
                return result

        return self._pass()

    # ------------------------------------------------------------------
    # Individual guards
    # ------------------------------------------------------------------

    def validate_runtime(self) -> GuardResult:
        if not self.runtime.connected:
            return self._fail("Runtime not connected")
        return self._pass()

    async def _validate_license(self, account: TradingAccount) -> GuardResult:
        if not account.license_id:
            return self._pass()
        try:
            async with async_session_factory() as session:
                lic_repo = LicenseRepository(session)
                lic = await lic_repo.get_by_id(account.license_id)
                if lic is None:
                    return self._fail("No license bound to account")
                if lic.status != "active":
                    return self._fail(f"License status: {lic.status}")
                if lic.expires_at and lic.expires_at < datetime.now(timezone.utc):
                    return self._fail("License expired")
        except Exception as e:
            logger.error("License check failed: %s", e)
            return self._fail("License check error")
        return self._pass()

    def _validate_engine(self) -> GuardResult:
        if not engine_manager.is_running(self.account_id):
            return self._fail("Engine not running")
        status = engine_manager.get_status(self.account_id)
        if status.error:
            return self._fail(f"Engine error: {status.error}")
        if status.state not in ("RUNNING", "STARTING"):
            return self._fail(f"Engine state: {status.state}")
        return self._pass()

    async def _validate_risk(self, account: TradingAccount) -> GuardResult:
        if not account.active:
            return self._fail("Account is paused")
        return self._pass()

    async def validate_symbol(self, symbol: str) -> GuardResult:
        try:
            symbols = await self.runtime.get_symbols()
            matched = [s for s in symbols if s.name == symbol]
            if not matched:
                return self._fail(f"Symbol {symbol} not found on account")
        except Exception as e:
            return self._fail(f"Symbol check error: {e}")
        return self._pass()

    async def validate_spread(self, symbol: str, max_spread: int = 50) -> GuardResult:
        try:
            info = await self._get_symbol_info(symbol)
            if info is None:
                return self._fail(f"Cannot check spread for {symbol}")
            if info.spread > max_spread:
                return self._fail(f"Spread too high: {info.spread} (max {max_spread})")
            if info.spread <= 0:
                self._warnings.append(f"Spread is 0 for {symbol}")
        except Exception as e:
            return self._fail(f"Spread check error: {e}")
        return self._pass()

    async def validate_market_open(self, symbol: str) -> GuardResult:
        try:
            info = await self._get_symbol_info(symbol)
            if info is None:
                return self._fail(f"Cannot check market status for {symbol}")
            if info.trade_mode == 0:
                return self._fail(f"Market closed for {symbol}")
        except Exception as e:
            return self._fail(f"Market check error: {e}")
        return self._pass()

    async def validate_news(self, symbol: str, minutes_before: int = 30,
                            calendar: Optional[Any] = None) -> GuardResult:
        try:
            from news_engine.news_filter import NewsFilter
            from news_engine.calendar import EconomicCalendar

            if calendar is None:
                calendar = EconomicCalendar()
                try:
                    from news_engine.news_cache import news_cache
                    events = await news_cache.get_events()
                    if events:
                        for ev in events:
                            calendar.add_event(ev.time, ev.currency, ev.event_name, ev.impact)
                except ImportError:
                    pass
                except Exception:
                    pass

            if len(calendar.get_events()) == 0:
                self._warnings.append("No news events loaded, skipping news guard")
                return self._pass()

            nf = NewsFilter(block_before_minutes=minutes_before)
            result = nf.evaluate(symbol, datetime.now(timezone.utc), calendar)
            if not result.allowed:
                return self._fail(f"News filter blocked: {result.reason}")
        except ImportError:
            self._warnings.append("NewsFilter not available, skipping news guard")
        except Exception as e:
            logger.error("News check error: %s", e)
            self._warnings.append(f"News check error: {e}")
        return self._pass()

    async def validate_calendar_news(self, symbol: str) -> GuardResult:
        """Check the Economic Calendar news risk window (Phase 3).

        Blocks NEW entries only when a HIGH/MEDIUM-impact USD event
        is within the configurable T-60 window.  Does NOT close existing
        positions.
        """
        try:
            from core_engine.risk.news_risk_window import news_risk_window

            if news_risk_window.is_entry_blocked(symbol):
                reason = news_risk_window.get_block_reason(symbol)
                return self._fail(reason or "News risk window active")
        except ImportError:
            self._warnings.append("NewsRiskWindow not available, skipping calendar news guard")
        except Exception as e:
            logger.error("Calendar news check error: %s", e)
            self._warnings.append(f"Calendar news check error: {e}")
        return self._pass()

    async def validate_duplicate_trade(self, symbol: str, direction: str) -> GuardResult:
        try:
            positions = await self.runtime.get_positions()
            for pos in positions:
                pos_dir = "BUY" if pos.type in (0, 2, 4) else "SELL"
                if pos.symbol == symbol and pos_dir == direction:
                    return self._fail(f"Duplicate trade: {symbol} {direction} already open")
        except Exception as e:
            logger.error("Duplicate check error: %s", e)
            self._warnings.append("Could not verify duplicate trades")
        return self._pass()

    async def validate_daily_limit(self, symbol: str, max_trades_per_symbol: int = 3,
                                   max_trades_total: int = 10) -> GuardResult:
        try:
            positions = await self.runtime.get_positions()
            symbol_count = sum(1 for p in positions if p.symbol == symbol)
            total_count = len(positions)
            if symbol_count >= max_trades_per_symbol:
                return self._fail(f"Symbol daily limit: {symbol_count}/{max_trades_per_symbol}")
            if total_count >= max_trades_total:
                return self._fail(f"Total daily limit: {total_count}/{max_trades_total}")
        except Exception as e:
            logger.error("Daily limit check error: %s", e)
            self._warnings.append("Could not verify daily limits")
        return self._pass()

    async def validate_session(self, symbol: str = "",
                               allowed_sessions: Optional[List[str]] = None) -> GuardResult:
        try:
            from core_engine.data_feed.session_manager import SessionManager
            mgr = SessionManager()
            now = datetime.now(timezone.utc)
            session = mgr.get_current_session(now)
            if session is None:
                return self._fail("Market session is closed")
            if allowed_sessions:
                if session.label.upper() not in [s.upper() for s in allowed_sessions]:
                    return self._fail(f"Session {session.label} not in allowed: {allowed_sessions}")
        except ImportError:
            self._warnings.append("SessionManager not available")
        except Exception as e:
            logger.error("Session check error: %s", e)
            self._warnings.append(f"Session check error: {e}")
        return self._pass()

    # ------------------------------------------------------------------
    # Real-trading specific gate
    # ------------------------------------------------------------------

    async def validate_real_trading(self, account: TradingAccount) -> GuardResult:
        if not ALLOW_REAL_TRADING:
            return self._fail("ALLOW_REAL_TRADING is false")
        if not account.real_trading_enabled:
            return self._fail("Account real_trading_enabled is false")
        if DEMO_ONLY:
            try:
                acc_info = await self.runtime.account_info()
                if not acc_info.is_demo:
                    return self._fail("DEMO_ONLY mode: account is not demo")
            except Exception as e:
                return self._fail(f"Cannot verify demo status: {e}")
        return self._pass()

    # ------------------------------------------------------------------
    # Full pre-flight checklist (returns all results, not just first fail)
    # ------------------------------------------------------------------

    async def full_checklist(self, symbol: str, direction: str,
                             account: Optional[TradingAccount] = None) -> Dict[str, GuardResult]:
        account = account or await self._load_account()
        if account is None:
            return {"account": self._fail("Account not found")}

        checks = {
            "runtime": self.validate_runtime(),
            "engine": self._validate_engine(),
            "license": await self._validate_license(account),
            "risk": await self._validate_risk(account),
            "symbol": await self.validate_symbol(symbol),
            "spread": await self.validate_spread(symbol),
            "market_open": await self.validate_market_open(symbol),
            "news": await self.validate_news(symbol),
            "calendar_news": await self.validate_calendar_news(symbol),
            "duplicate": await self.validate_duplicate_trade(symbol, direction),
            "daily_limit": await self.validate_daily_limit(symbol),
            "session": await self.validate_session(symbol),
            "real_trading": await self.validate_real_trading(account),
        }

        for name, result in checks.items():
            if not result.allowed:
                await self._log_block(name, result.reason, symbol, direction)

        return checks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _load_account(self) -> Optional[TradingAccount]:
        try:
            async with async_session_factory() as session:
                repo = AccountRepository(session)
                return await repo.get_by_id(self.account_id)
        except Exception as e:
            logger.error("Failed to load account %s: %s", self.account_id, e)
            return None

    async def _get_symbol_info(self, symbol: str) -> Optional[MTSymbolInfo]:
        try:
            symbols = await self.runtime.get_symbols()
            for s in symbols:
                if s.name == symbol:
                    return s
        except Exception:
            pass
        return None

    async def _validate_risk_guard(self, guard_name: str,
                                    account: TradingAccount) -> GuardResult:
        risk: Optional[RiskProfile] = account.risk_profile
        if risk is None:
            self._warnings.append(f"No risk profile for {self.account_id}")
            return self._pass()

        if risk.day_start_equity is None or risk.initial_balance is None:
            self._warnings.append("Risk baselines not yet initialized")
            return self._pass()

        try:
            acc_info = await self.runtime.account_info()
            current_equity = acc_info.equity
        except Exception as e:
            return self._fail(f"Cannot get equity for {guard_name} check: {e}")

        mode_map = {"ultra_conservative": 0.10, "conservative": 0.25, "balanced": 0.50, "aggressive": 1.0}
        risk_pct = float(risk.max_risk_trade) if risk.max_risk_trade else mode_map.get(risk.mode or "balanced", 0.5)
        profile_builder = AccountProfileBuilder()
        profile = profile_builder.create_profile(
            client_id=account.id,
            account_type=account.account_type or "PERSONAL",
            balance=risk.day_start_balance or risk.initial_balance or 0,
            equity=current_equity,
            currency=account.currency or "USD",
            custom_settings={
                "risk_per_trade": risk_pct,
                "max_daily_loss": risk.daily_loss or 3.0,
                "max_account_loss": risk.max_loss or 10.0,
            },
            use_recommended_settings=False,
            custom_settings_acknowledged=True,
        )

        if guard_name == "daily_loss":
            guard = DailyLossGuard()
            result = guard.evaluate(
                profile=profile,
                current_equity=current_equity,
                daily_start_equity=risk.day_start_equity,
            )
            if not result.allowed:
                return self._fail(
                    f"Daily loss limit: {result.daily_loss_percent:.1f}% "
                    f"(max {result.max_daily_loss_percent:.1f}%)"
                )
            if result.warning:
                self._warnings.append(result.warning)

        elif guard_name == "max_loss":
            guard = MaxLossGuard()
            result = guard.evaluate(
                profile=profile,
                current_equity=current_equity,
                start_balance=risk.initial_balance,
            )
            if not result.allowed:
                return self._fail(
                    f"Max loss limit: {result.total_loss_percent:.1f}% "
                    f"(max {result.max_account_loss_percent:.1f}%)"
                )
            if result.warning:
                self._warnings.append(result.warning)

        return self._pass()

    # ------------------------------------------------------------------
    # Position management guard
    # ------------------------------------------------------------------

    async def can_manage_position(self, account: Optional[TradingAccount] = None,
                                  position: Optional["MTPosition"] = None) -> GuardResult:
        self._warnings = []

        account = account or await self._load_account()
        if account is None:
            result = self._fail("Account not found")
            await self._log_block("account", "Account not found", position.symbol if position else "")
            return result

        for check_name, check in (("runtime", self.validate_runtime),
                                  ("engine", self._validate_engine)):
            result = check()
            if not result.allowed:
                return result

        for check_name, check in (("license", self._validate_license),
                                  ("risk", self._validate_risk)):
            result = await check(account)
            if not result.allowed:
                return result

        return self._pass()

    async def _log_block(self, check_name: str, reason: str,
                         symbol: str = "", direction: str = "",
                         extra: Optional[dict] = None) -> None:
        payload: dict = {
            "guard_check": check_name,
            "reason": reason,
            "symbol": symbol,
            "direction": direction,
        }
        if extra:
            payload.update(extra)

        # 1. Publish to event bus → AlertService sends Telegram
        try:
            event_bus.publish(EventType.TRADE_BLOCKED.value, {
                "event_type": EventType.TRADE_BLOCKED.value,
                "account_id": self.account_id,
                "user_id": self.user_id,
                "message": f"🚫 Guard blocked: {check_name} - {reason}",
                "data": payload,
            })
        except Exception as e:
            logger.warning("Failed to publish guard block event: %s", e)

        # 2. Write directly to AuditLog
        try:
            from core_engine.audit.audit_logger import audit_logger
            await audit_logger.log_event(
                event_type=EventType.TRADE_BLOCKED.value,
                message=f"Guard blocked: {check_name} - {reason}",
                account_id=self.account_id,
                user_id=self.user_id,
                payload=payload,
                source="execution",
            )
        except Exception as e:
            logger.warning("Failed to log guard block to audit: %s", e)
