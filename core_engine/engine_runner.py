from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from core_engine.config.trading_modes import get_trading_mode
from core_engine.risk.symbol_validator import SymbolValidator

from sqlalchemy import select

from database.db import async_session_factory
from database.models import TradingAccount
from database.repositories import AccountRepository
from core_engine.account_manager import AccountManager
from core_engine.mt5_runtime import MT5Runtime
from core_engine.risk.account_profile import AccountProfile, AccountProfileBuilder
from core_engine.detection.setup_detector import SetupDetector, SetupCandidate
from core_engine.data_feed.market_data import MarketData
from core_engine.execution.execution_engine import ExecutionEngine, ExecutionResult
from core_engine.execution.execution_guard import ExecutionGuard
from core_engine.execution.trade_manager import TradeManager, TradeManagementAction
from core_engine.execution.trade_planner import TradePlan, TradePlanner
from core_engine.execution.paper_trading import paper_trading
from core_engine.execution.trade_lifecycle import trade_lifecycle
from core_engine.health.heartbeat import HeartbeatSender
from core_engine.health.health_monitor import health_monitor
from core_engine.version import ENGINE_VERSION
from core_engine.mt_runtime import (
    MTRuntime,
    MTConnectionConfig,
    MTPosition,
    create_mt_runtime,
)
from core_engine.engine_manager import engine_manager
from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType
from renderer_bridge.setup_mapper import setup_to_snapshot as _setup_to_snapshot
from config.settings import DEMO_ONLY

logger = logging.getLogger(__name__)


@dataclass
class EngineEvent:
    account_id: str
    user_id: str
    event_type: str
    message: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EngineRunner(HeartbeatSender):
    def __init__(
        self,
        detect_interval: float = 30.0,
        manage_interval: float = 5.0,
    ):
        super().__init__()
        self.detect_interval = detect_interval
        self.manage_interval = manage_interval
        self._tasks: Dict[str, asyncio.Task] = {}
        self._runtimes: Dict[str, MTRuntime] = {}
        self._running = False
        self._detectors: Dict[str, SetupDetector] = {}
        self._profile_builder = AccountProfileBuilder()

        self._last_detection_heartbeat = 0.0
        self._heartbeat_interval_seconds = 30.0
        self._debug_counters: dict[str, int] = {
            "cycles": 0,
            "symbols_seen": 0,
            "symbols_allowed": 0,
            "symbols_blocked": 0,
            "empty_data": 0,
            "detector_calls": 0,
            "detector_timeouts": 0,
            "detector_errors": 0,
            "setups_found": 0,
            "score_rejected": 0,
            "setups_published": 0,
            "setups_skipped_dedup": 0,
            "setups_skipped_active": 0,
        }
        self._processed_setups: set[str] = set()

    async def _build_runtime(self, account_id: str) -> Optional[MTRuntime]:
        async with async_session_factory() as session:
            repo = AccountRepository(session)
            account = await repo.get_by_id(account_id)
            if not account or not account.server or not account.login:
                return None
            from security.encryption import decrypt
            password = decrypt(account.encrypted_password) if account.encrypted_password else ""
            config = MTConnectionConfig(
                server=account.server,
                login=account.login,
                password=password,
                platform=account.platform or "MT5",
            )
            mt = create_mt_runtime(config)
            await mt.connect()
            return mt

    async def _build_profile(self, account_id: str) -> Optional[AccountProfile]:
        async with async_session_factory() as session:
            repo = AccountRepository(session)
            account = await repo.get_by_id(account_id)
            if not account:
                return None
            risk = account.risk_profile
            balance = account.balance_snapshot or account.account_size or 0.0

            if risk:
                mode_map = {"ultra_conservative": 0.10, "conservative": 0.25, "balanced": 0.50, "aggressive": 1.0}
                risk_pct = float(risk.max_risk_trade) if risk.max_risk_trade else mode_map.get(risk.mode or "balanced", 0.5)
                custom_settings = {
                    "risk_per_trade": risk_pct,
                    "max_daily_loss": float(risk.daily_loss) if risk.daily_loss else 3.0,
                    "max_account_loss": float(risk.max_loss) if risk.max_loss else 10.0,
                }
            else:
                custom_settings = None

            return self._profile_builder.create_profile(
                client_id=account.id,
                account_type=account.account_type or "PERSONAL",
                balance=float(balance),
                equity=float(account.equity_snapshot or balance),
                broker=account.broker,
                prop_firm=account.prop_firm,
                currency=account.currency or "USD",
                use_recommended_settings=not bool(risk),
                custom_settings_acknowledged=False,
                custom_settings=custom_settings,
            )

    def _publish(self, account_id: str, user_id: str, event_type: str, message: str, data: dict = None):
        ev = EngineEvent(
            account_id=account_id,
            user_id=user_id,
            event_type=event_type,
            message=message,
            data=data or {},
        )
        payload_data = data or {}
        event_bus.publish(event_type, {
            "account_id": account_id,
            "user_id": user_id,
            "event_type": event_type,
            "trade_id": str(payload_data.get("ticket", "")),
            "message": message,
            "data": payload_data,
            "timestamp": ev.timestamp.isoformat(),
        })

    def _log_detection_heartbeat(
        self,
        *,
        account_id: str,
        trade_mode: str,
        symbols: list[str],
    ) -> None:
        now = time.monotonic()
        if now - self._last_detection_heartbeat < self._heartbeat_interval_seconds:
            return
        self._last_detection_heartbeat = now
        logger.info(
            "Detection heartbeat | account=%s mode=%s symbols=%s counters=%s",
            account_id, trade_mode, symbols, self._debug_counters,
        )

    async def _detect_and_execute(
        self,
        account_id: str,
        user_id: str,
        runtime: MTRuntime,
        profile: AccountProfile,
        market_data: MarketData,
        real_trading_enabled: bool = False,
        trade_mode: str = "CONSERVATIVE",
    ):
        try:
            self._debug_counters["cycles"] += 1

            raw_symbols = [s.name for s in await runtime.get_symbols()]
            logger.info("Symbols loaded from runtime: count=%d samples=%s", len(raw_symbols), raw_symbols[:5])

            mode_config = get_trading_mode(trade_mode)

            # --- Symbol normalization & mode filtering ---
            normalizer = SymbolValidator()
            normalized_allowed = {s.upper() for s in (mode_config.allowed_symbols or [])}
            filtered_symbols = []
            for s in raw_symbols:
                self._debug_counters["symbols_seen"] += 1
                raw_upper = s.upper().replace(" ", "")
                normalized = normalizer.normalize_symbol(raw_upper)
                logger.debug("Symbol normalization | broker=%s raw=%s normalized=%s", s, raw_upper, normalized)

                if normalized_allowed:
                    in_allowed = (raw_upper in normalized_allowed) or (normalized in normalized_allowed)
                    if not in_allowed:
                        self._debug_counters["symbols_blocked"] += 1
                        logger.debug("Symbol blocked by mode | broker=%s normalized=%s mode=%s allowed=%s",
                                     s, normalized, trade_mode, normalized_allowed)
                        continue
                self._debug_counters["symbols_allowed"] += 1
                filtered_symbols.append(s)

            logger.info("Symbol filtering | total=%d blocked=%d allowed=%d mode=%s",
                        len(raw_symbols),
                        self._debug_counters["symbols_blocked"],
                        self._debug_counters["symbols_allowed"],
                        trade_mode)

            symbols = filtered_symbols if normalized_allowed else raw_symbols
            scan_targets = symbols[:15]
            logger.info("Scan targets | mode=%s count=%d symbols=%s", trade_mode, len(scan_targets), scan_targets)

            self._log_detection_heartbeat(
                account_id=account_id,
                trade_mode=trade_mode,
                symbols=scan_targets,
            )

            detector = self._detectors.get(account_id) or SetupDetector()
            self._detectors[account_id] = detector

            is_real = isinstance(runtime, MT5Runtime)
            allow_execution = False
            if is_real and real_trading_enabled:
                if DEMO_ONLY:
                    try:
                        acc_info = await runtime.account_info()
                        allow_execution = acc_info.is_demo
                    except Exception:
                        allow_execution = False
                else:
                    allow_execution = True

            sem = asyncio.Semaphore(5)
            async def _detect_one(symbol: str):
                async with sem:
                    self._debug_counters["detector_calls"] += 1
                    try:
                        return symbol, await asyncio.wait_for(
                            detector.detect(market_data, symbol, "M5"),
                            timeout=20.0,
                        )
                    except asyncio.TimeoutError:
                        self._debug_counters["detector_timeouts"] += 1
                        logger.error("Detector timeout | account=%s symbol=%s timeout=20s", account_id, symbol)
                        return symbol, None
                    except Exception:
                        self._debug_counters["detector_errors"] += 1
                        logger.exception("Detector failed | account=%s symbol=%s", account_id, symbol)
                        return symbol, None

            results = await asyncio.gather(
                *(_detect_one(s) for s in scan_targets),
                return_exceptions=False,
            )

            published_in_cycle = 0
            for symbol, candidate in results:
                if candidate is None:
                    per_sym = getattr(detector, '_per_symbol_results', {}).get(symbol, {})
                    if per_sym.get("rejected"):
                        self._debug_counters["score_rejected"] += 1
                        logger.info("Score reject via last_detect_result | symbol=%s score=%.1f recommendation=%s",
                                    symbol, per_sym.get("score", 0), per_sym.get("recommendation", "REJECT"))
                    continue

                self._debug_counters["setups_found"] += 1
                logger.info("Detector found setup | symbol=%s score=%.2f direction=%s reasons=%s",
                            symbol, candidate.score or 0, candidate.direction, candidate.reasons)

                if candidate.score_result and candidate.score_result.recommendation != "EXECUTE":
                    self._debug_counters["score_rejected"] += 1
                    logger.info("Setup rejected by score | symbol=%s score=%.2f recommendation=%s mode=%s",
                                symbol, candidate.score or 0, candidate.score_result.recommendation, trade_mode)
                    continue

                candidate_id = candidate.setup_id or f"{symbol}_{candidate.direction}_{int(time.time()*1000)}"
                logger.info("Setup accepted | symbol=%s candidate_id=%s score=%.2f direction=%s mode=%s",
                            symbol, candidate_id, candidate.score or 0, candidate.direction, trade_mode)

                # Guard: skip if active trade exists for same symbol+direction
                if await paper_trading.has_active_trade(account_id, symbol, candidate.direction):
                    self._debug_counters["setups_skipped_active"] += 1
                    logger.info("Setup skipped (active trade) | symbol=%s direction=%s", symbol, candidate.direction)
                    continue

                # Dedup: skip if same (symbol, direction, candle_M5) already published
                candle_ts = int(time.time() / 300) * 300
                dedup_key = f"{symbol}:{candidate.direction}:{candle_ts}"
                if dedup_key in self._processed_setups:
                    self._debug_counters["setups_skipped_dedup"] += 1
                    logger.info("Setup skipped (dedup) | symbol=%s direction=%s candle=%s",
                                symbol, candidate.direction, candle_ts)
                    continue

                planner = TradePlanner()
                current_price = await self._get_current_price(runtime, symbol, candidate.direction)
                plan = planner.plan(candidate, profile, current_price)
                # Inject plan values into candidate so snapshot has Entry/SL/TP
                if plan.valid:
                    candidate.entry_zone = {"entry_price": plan.entry_price}
                    candidate.stop_loss = plan.stop_loss
                    candidate.take_profit = plan.take_profit
                snapshot = _setup_to_snapshot(candidate)
                candidate_data = {"symbol": symbol, "direction": candidate.direction,
                     "score": candidate.score, "rank": candidate.rank,
                     "confidence": candidate.confidence_score,
                     "reasons": candidate.reasons, "candidate_id": candidate_id,
                     "snapshot": snapshot, "timeframe": candidate.timeframe,
                     "entry_price": plan.entry_price if plan.valid else None,
                     "stop_loss": plan.stop_loss if plan.valid else None,
                     "take_profit": plan.take_profit if plan.valid else None,
                     "lot_size": plan.lot_size if plan.valid else 0,
                     "risk_reward": plan.risk_reward if plan.valid else 0,
                     "session": candidate.session.current_session.label if candidate.session and candidate.session.current_session else None}

                logger.info("Publishing SETUP_DETECTED | candidate_id=%s account=%s symbol=%s direction=%s score=%.2f",
                            candidate_id, account_id, symbol, candidate.direction, candidate.score or 0)
                self._publish(
                    account_id, user_id, EventType.SETUP_DETECTED.value,
                    f"Setup: {symbol} {candidate.direction} score={candidate.score:.0f}",
                    candidate_data,
                )
                self._debug_counters["setups_published"] += 1
                published_in_cycle += 1
                self._processed_setups.add(dedup_key)
                logger.info("SETUP_DETECTED published | candidate_id=%s symbol=%s candle_key=%s", candidate_id, symbol, candle_ts)

                if is_real and not allow_execution:
                    if plan.valid:
                        session_label = candidate_data.get("session")
                        trade = await paper_trading.create_from_plan(
                            account_id, user_id, candidate, plan,
                            session_name=session_label,
                            candidate_id=candidate_id,
                        )
                        plan_data = paper_trading.build_plan_data(trade, plan)
                        plan_data["snapshot"] = _setup_to_snapshot(candidate)
                        plan_data["timeframe"] = candidate.timeframe
                        self._publish(
                            account_id, user_id, EventType.PAPER_TRADE_PLANNED.value,
                            f"Paper: {symbol} {candidate.direction} @ {plan.entry_price} "
                            f"SL={plan.stop_loss} TP={plan.take_profit} "
                            f"lot={plan.lot_size} RR={plan.risk_reward:.1f}",
                            plan_data,
                        )
                    else:
                        self._publish(
                            account_id, user_id, EventType.PAPER_TRADE_REJECTED.value,
                            f"Plan rejected for {symbol}: no valid plan",
                            {"symbol": symbol, "direction": candidate.direction, "candidate_id": candidate_id},
                        )
                    continue

                engine = ExecutionEngine(runtime, account_id=account_id, user_id=user_id)
                result = await engine.execute_candidate(candidate, profile, current_price, account_id=account_id, user_id=user_id, trade_mode=trade_mode)
                if result.success:
                    real_filled = 0.0
                    if getattr(result, "order", None) is not None:
                        real_filled = float(getattr(result.order, "filled_price", 0.0) or 0.0)
                    self._publish(
                        account_id, user_id, EventType.TRADE_OPENED.value,
                        f"Order placed: {symbol} {candidate.direction} lot={result.plan.lot_size}",
                        {"symbol": symbol, "direction": candidate.direction,
                         "lot_size": result.plan.lot_size,
                         "entry": result.plan.entry_price,
                         "filled_price": real_filled or plan.entry_price,
                         "sl": result.plan.stop_loss, "tp": result.plan.take_profit,
                         "ticket": result.order.order_id, "candidate_id": candidate_id,
                         "risk_reward": result.plan.risk_reward,
                         "session": candidate_data.get("session"),
                         "snapshot": snapshot},
                    )
                else:
                    self._publish(
                        account_id, user_id, EventType.SYSTEM_INFO.value,
                        f"Setup rejected: {symbol} - {result.message}",
                        {"symbol": symbol, "direction": candidate.direction, "candidate_id": candidate_id},
                    )

            # Cleanup old dedup entries (keep only last 30 min)
            cutoff = int(time.time() / 300) * 300 - 3600
            self._processed_setups = {k for k in self._processed_setups if k.count(":") >= 2 and int(k.split(":")[-1]) > cutoff}

            logger.info("Cycle complete | account=%s scan_targets=%d published=%d counters=%s",
                        account_id, len(scan_targets), published_in_cycle, self._debug_counters)
        except Exception as e:
            logger.exception("Detection failed for %s", account_id)

    async def _manage_positions(
        self,
        account_id: str,
        user_id: str,
        runtime: MTRuntime,
    ):
        try:
            positions = await runtime.get_positions()
            if not positions:
                return

            guard = ExecutionGuard(runtime, account_id, user_id)
            guard_result = await guard.can_manage_position(position=positions[0])
            if not guard_result.allowed:
                return

            trade_mgr = TradeManager(runtime)
            for pos in positions:
                plan = self._build_plan_from_position(pos)
                if plan is None:
                    continue
                actions = await trade_mgr.tick(pos, plan)
                for action in actions:
                    event_type = self._action_event_type(action.action)
                    self._publish(
                        account_id, user_id, event_type,
                        action.message,
                        {"ticket": action.ticket, "new_sl": action.new_sl,
                         "close_volume": action.close_volume},
                    )
        except Exception as e:
            logger.exception("Position management failed for %s", account_id)

    def _build_plan_from_position(self, pos: MTPosition) -> Optional[TradePlan]:
        direction = "BUY" if pos.type in (0, 2, 4) else "SELL"
        return TradePlan(
            valid=True, symbol=pos.symbol, direction=direction,
            entry_type="MARKET", entry_price=pos.open_price,
            stop_loss=pos.stop_loss, take_profit=pos.take_profit,
            risk_reward=0.0, lot_size=pos.volume, risk_percent=0.0,
        )

    def _action_event_type(self, action: str) -> str:
        mapping = {
            "MOVE_BE": EventType.BREAK_EVEN_MOVED.value,
            "PARTIAL_CLOSE": EventType.PARTIAL_CLOSE.value,
            "TRAIL_SL": EventType.TRAILING_STOP_UPDATED.value,
            "CLOSE": EventType.TRADE_CLOSED.value,
        }
        return mapping.get(action, EventType.TRADE_UPDATED.value)

    async def _get_real_trading_enabled(self, account_id: str) -> bool:
        try:
            async with async_session_factory() as session:
                repo = AccountRepository(session)
                account = await repo.get_by_id(account_id)
                if account:
                    return bool(account.real_trading_enabled)
        except Exception:
            pass
        return False

    async def _get_trade_mode(self, account_id: str) -> str:
        try:
            async with async_session_factory() as session:
                repo = AccountRepository(session)
                account = await repo.get_by_id(account_id)
                if account and account.trade_mode:
                    return account.trade_mode.upper()
        except Exception:
            pass
        return "CONSERVATIVE"

    async def _get_current_price(self, runtime: MTRuntime, symbol: str, direction: str = "BUY") -> float:
        """Real-time price via tick bid/ask with get_rates fallback.

        For SELL uses bid (exit price), for BUY uses ask (entry price).
        """
        try:
            ticks = await runtime.get_ticks(symbol, 1)
            if ticks:
                tick = ticks[0]
                return tick.bid if direction == "SELL" else tick.ask
        except Exception:
            pass
        try:
            raw = await runtime.get_rates(symbol, 1, 1)
            if raw and isinstance(raw, list) and len(raw) > 0:
                last = raw[-1]
                if isinstance(last, dict):
                    close = last.get("close") or last.get("Close", 0.0)
                    if close and float(close) > 0:
                        logger.warning("Using get_rates fallback for %s (no tick data)", symbol)
                        return float(close)
        except Exception:
            pass
        logger.warning("Could not determine current price for %s", symbol)
        return 0.0

    async def _detect_loop(self, account_id: str, user_id: str):
        logger.info("Engine detection loop started for %s", account_id)
        runtime = await self._build_runtime(account_id)
        if not runtime:
            logger.error("Cannot start engine for %s: no runtime", account_id)
            return
        self._runtimes[account_id] = runtime

        profile = await self._build_profile(account_id)
        if not profile:
            logger.error("Cannot start engine for %s: no profile", account_id)
            return

        real_trading_enabled = await self._get_real_trading_enabled(account_id)
        trade_mode = await self._get_trade_mode(account_id)

        market_data = MarketData(runtime)

        try:
            while self._running:
                if not engine_manager.is_running(account_id):
                    await asyncio.sleep(self.detect_interval)
                    continue

                t0 = time.monotonic()
                await self._detect_and_execute(
                    account_id, user_id, runtime, profile, market_data,
                    real_trading_enabled=real_trading_enabled,
                    trade_mode=trade_mode,
                )
                elapsed_ms = (time.monotonic() - t0) * 1000

                health_monitor.increment_metric("detection_cycles")
                health_monitor.record_latency("detection", elapsed_ms)
                self.send_heartbeat(
                    latency_ms=elapsed_ms,
                    message=f"Detection cycle for {account_id}",
                )
                await asyncio.sleep(self.detect_interval)
        except asyncio.CancelledError:
            logger.info("Detection loop cancelled for %s", account_id)
            raise
        except Exception:
            logger.exception("Detection loop crashed for %s", account_id)
            raise

    async def _manage_loop(self, account_id: str, user_id: str):
        logger.info("Engine management loop started for %s", account_id)
        try:
            while self._running:
                if not engine_manager.is_running(account_id):
                    await asyncio.sleep(self.manage_interval)
                    continue

                runtime = self._runtimes.get(account_id)
                if runtime:
                    t0 = time.monotonic()
                    await self._manage_positions(account_id, user_id, runtime)
                    elapsed_ms = (time.monotonic() - t0) * 1000
                    health_monitor.record_latency("execution", elapsed_ms)
                await asyncio.sleep(self.manage_interval)
        except asyncio.CancelledError:
            logger.info("Management loop cancelled for %s", account_id)
            raise
        except Exception:
            logger.exception("Management loop crashed for %s", account_id)
            raise

    async def _lifecycle_loop(self, account_id: str, user_id: str):
        logger.info("Trade lifecycle loop started for %s", account_id)
        try:
            while self._running:
                if not engine_manager.is_running(account_id):
                    await asyncio.sleep(self.manage_interval)
                    continue
                runtime = self._runtimes.get(account_id)
                if runtime:
                    try:
                        active = await trade_lifecycle.get_active_trades(account_id)
                        for trade in active:
                            current_price = await self._get_current_price(runtime, trade.symbol, trade.direction)
                            if current_price <= 0:
                                continue
                            if trade.status == "PLANNED":
                                if trade_lifecycle.check_fill(trade, current_price):
                                    filled = await trade_lifecycle.fill_trade(trade.id, current_price)
                                    if filled:
                                        self._publish(
                                            account_id, user_id, EventType.PAPER_TRADE_FILLED.value,
                                            f"Filled: {trade.symbol} {trade.direction} @ {current_price:.2f}",
                                            {"id": trade.id, "symbol": trade.symbol,
                                             "direction": trade.direction, "entry_price": current_price,
                                             "lot_size": trade.lot_size,
                                             "candidate_id": trade.candidate_id or ""},
                                        )
                            elif trade.status == "FILLED":
                                await trade_lifecycle.track_price(trade.id, current_price)
                                if not trade.partial_closed and trade_lifecycle.check_partial_trigger(trade, current_price):
                                    partial = await trade_lifecycle.execute_partial_close(trade.id, current_price)
                                    if partial:
                                        self._publish(
                                            account_id, user_id, EventType.PARTIAL_CLOSE.value,
                                            f"Partial: {trade.symbol} {trade.direction} @ {current_price:.2f} "
                                            f"PnL={partial.partial_pnl:.2f} remaining={partial.lot_size:.4f}",
                                            {"id": trade.id, "symbol": trade.symbol,
                                             "direction": trade.direction,
                                             "partial_price": current_price,
                                             "partial_pnl": partial.partial_pnl,
                                             "remaining_volume": partial.lot_size,
                                             "candidate_id": trade.candidate_id or ""},
                                        )
                                        self._publish(
                                            account_id, user_id, EventType.BREAK_EVEN_MOVED.value,
                                            f"BE: {trade.symbol} {trade.direction} "
                                            f"SL moved to {partial.breakeven_price:.2f}",
                                            {"id": trade.id, "symbol": trade.symbol,
                                             "direction": trade.direction,
                                             "breakeven_price": partial.breakeven_price,
                                             "candidate_id": trade.candidate_id or ""},
                                        )
                                        continue
                                if trade_lifecycle.check_tp(trade, current_price):
                                    closed = await trade_lifecycle.hit_tp(trade.id, current_price)
                                    if closed:
                                        self._publish(
                                            account_id, user_id, EventType.PAPER_TRADE_TP_HIT.value,
                                            f"TP: {trade.symbol} {trade.direction} @ {current_price:.2f} "
                                            f"PnL={closed.realized_pnl:.2f}",
                                            {"id": trade.id, "symbol": trade.symbol,
                                             "direction": trade.direction,
                                             "exit_price": current_price,
                                             "realized_pnl": closed.realized_pnl,
                                             "candidate_id": trade.candidate_id or ""},
                                        )
                                elif trade_lifecycle.check_sl(trade, current_price):
                                    closed = await trade_lifecycle.hit_sl(trade.id, current_price)
                                    if closed:
                                        self._publish(
                                            account_id, user_id, EventType.PAPER_TRADE_SL_HIT.value,
                                            f"SL: {trade.symbol} {trade.direction} @ {current_price:.2f} "
                                            f"PnL={closed.realized_pnl:.2f}",
                                            {"id": trade.id, "symbol": trade.symbol,
                                             "direction": trade.direction,
                                             "exit_price": current_price,
                                             "realized_pnl": closed.realized_pnl,
                                             "candidate_id": trade.candidate_id or ""},
                                        )
                                elif trade_lifecycle.check_be_activation(trade, current_price):
                                    be = await trade_lifecycle.activate_breakeven(trade.id)
                                    if be:
                                        self._publish(
                                            account_id, user_id, EventType.BREAK_EVEN_MOVED.value,
                                            f"BE: {trade.symbol} {trade.direction} "
                                            f"SL moved to {be.breakeven_price:.2f}",
                                            {"id": trade.id, "symbol": trade.symbol,
                                             "direction": trade.direction,
                                             "breakeven_price": be.breakeven_price,
                                             "candidate_id": trade.candidate_id or ""},
                                        )
                    except Exception:
                        logger.exception("Lifecycle check failed for %s", account_id)
                await asyncio.sleep(self.manage_interval)
        except asyncio.CancelledError:
            logger.info("Lifecycle loop cancelled for %s", account_id)
            raise
        except Exception:
            logger.exception("Lifecycle loop crashed for %s", account_id)
            raise

    async def start_engine(self, account_id: str, user_id: str) -> None:
        if account_id in self._tasks:
            logger.warning("Engine already running for %s", account_id)
            return
        self.start_heartbeat(
            component=f"EngineRunner:{account_id}",
            interval=30.0,
            account_id=account_id,
            version=ENGINE_VERSION,
        )
        detect_task = asyncio.create_task(self._detect_loop(account_id, user_id))
        manage_task = asyncio.create_task(self._manage_loop(account_id, user_id))
        lifecycle_task = asyncio.create_task(self._lifecycle_loop(account_id, user_id))
        self._tasks[account_id] = (detect_task, manage_task, lifecycle_task)

    async def stop_engine(self, account_id: str) -> None:
        await self.stop_heartbeat()
        tasks = self._tasks.pop(account_id, None)
        if tasks:
            for t in tasks:
                if not t.done():
                    t.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Engine shutdown timeout for %s — forcing", account_id)
        rt = self._runtimes.pop(account_id, None)
        if rt:
            try:
                await rt.disconnect()
            except Exception:
                pass
        self._detectors.pop(account_id, None)

    async def start_all(self) -> None:
        self._running = True
        async with async_session_factory() as session:
            stmt = select(TradingAccount).where(TradingAccount.active == True)
            result = await session.execute(stmt)
            accounts = list(result.scalars().all())
        for acc in accounts:
            await engine_manager.start(acc.id)
            await self.start_engine(acc.id, acc.user_id)

    async def stop_all(self) -> None:
        self._running = False
        ids = list(self._tasks.keys())
        if ids:
            await asyncio.gather(
                *(self.stop_engine(aid) for aid in ids),
                return_exceptions=True,
            )

    def is_running(self, account_id: str) -> bool:
        return account_id in self._tasks


engine_runner = EngineRunner()
