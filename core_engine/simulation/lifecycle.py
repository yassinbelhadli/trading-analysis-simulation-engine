"""Trade Lifecycle — state machine that manages a trade from PENDING to CLOSED.

States:
    PENDING   → entry not yet filled
    FILLED    → entry filled, monitoring TP/SL
    TP1_HIT   → first take-profit hit, may move SL to BE
    BE_SET    → stop moved to breakeven
    TP2_HIT   → second take-profit hit, may activate trailing
    TRAILING  → trailing stop active
    TP3_HIT   → (or more) final TP hit
    STOPPED   → stop loss hit
    CLOSED    → all TPs hit, trade complete
    EXPIRED   → entry never filled (limit/stop expired)

Dual mode:
    - Simulation:  step() scans candles for TP/SL
    - Execution:   apply_broker_event() processes broker events directly
    Both modes share the same state machine, partials, BE, trailing logic.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict

from .planner import TradePlan
from .result import TradeState, TradeEvent
from .fill_model import FillModel, FillResult
from .partials import PartialTracker
from .breakeven import BreakevenManager
from .trailing import TrailingManager


class LifecycleResult:
    """Result of a lifecycle step."""
    def __init__(self, state: str, events: List[TradeEvent], done: bool = False):
        self.state = state
        self.events = events
        self.done = done


class TradeLifecycle:
    """State machine for a single trade.

    Usage:
        lc = TradeLifecycle(plan, fill_model)
        lc.start(candles, entry_idx)

        for i in range(entry_idx + 1, len(candles)):
            result = lc.step(candles, i)
            if result.done:
                break
    """

    def __init__(self, plan: TradePlan, fill_model: FillModel = None):
        self.plan = plan
        self.fill = FillModel() if fill_model is None else fill_model

        self.state = TradeState.PENDING
        self.events: List[TradeEvent] = []
        self.fill_info: Optional[FillResult] = None
        self.entry_idx: int = -1
        self.last_check_idx: int = -1

        # Sub-managers
        self.partials = PartialTracker(plan)
        self.breakeven = BreakevenManager()
        self.trailing = TrailingManager()

        # Current active stop
        self.current_sl: float = plan.stop_loss
        self.current_tp_index: int = 0
        self.total_r: float = 0.0
        self.total_pnl: float = 0.0

    def start(self, candles: List[Dict], idx: int) -> LifecycleResult:
        """Attempt to fill entry at candle idx."""
        result = self.fill.fill_entry(self.plan, candles, idx)
        if result.filled:
            self.state = TradeState.FILLED
            self.fill_info = result
            self.entry_idx = idx
            self.last_check_idx = idx
            self.current_sl = self.plan.stop_loss
            self.events.append(TradeEvent(
                time=str(candles[idx].get("time", "")),
                state=TradeState.FILLED,
                price=result.price,
                description=f"Entry filled at {result.price} ({result.fill_type})",
            ))
            return LifecycleResult(TradeState.FILLED, self.events[-1:])
        else:
            return LifecycleResult(TradeState.PENDING, [])

    def step(self, candles: List[Dict], idx: int) -> LifecycleResult:
        """Advance the lifecycle by one candle.

        Returns:
            LifecycleResult with new state and any events generated.
        """
        if self.state in (TradeState.CLOSED, TradeState.STOPPED, TradeState.EXPIRED):
            return LifecycleResult(self.state, [], done=True)

        new_events = []
        _add = lambda ev: (self.events.append(ev), new_events.append(ev))

        # ── Check SL first — highest priority ──
        if self.state != TradeState.PENDING:
            if self.fill.check_sl_hit(self.plan, candles, idx, self.last_check_idx):
                sl_price = self.current_sl
                hit_price = self._get_sl_hit_price(candles, idx, self.last_check_idx)
                self.state = TradeState.STOPPED
                # Calculate actual R multiple from SL to entry
                if self.plan.side == "BUY":
                    r = (sl_price - self.plan.entry) / self.plan.risk_distance if self.plan.risk_distance else -1.0
                else:
                    r = (self.plan.entry - sl_price) / self.plan.risk_distance if self.plan.risk_distance else -1.0
                self.total_r += r * self.partials.remaining_ratio
                _add(TradeEvent(
                    time=str(candles[idx].get("time", "")),
                    state=TradeState.STOPPED,
                    price=hit_price or sl_price,
                    description=f"Stop Loss hit at {hit_price or sl_price}",
                    pnl=round(self.total_pnl, 2),
                    rr=round(self.total_r, 2),
                ))
                self.last_check_idx = idx
                return LifecycleResult(TradeState.STOPPED, new_events, done=True)

        # ── Check trailing stop ──
        if self.state == TradeState.TRAILING:
            self.trailing.update(
                self.plan,
                candles[idx].get("close", 0),
                candles[idx].get("high", 0),
                candles[idx].get("low", 0),
            )
            if self.trailing.current_stop != self.current_sl:
                self.current_sl = self.trailing.current_stop
                _add(TradeEvent(
                    time=str(candles[idx].get("time", "")),
                    state=TradeState.TRAILING,
                    price=self.current_sl,
                    description=f"Trailing stop moved to {self.current_sl:.2f}",
                ))
            # Check trailing breach
            trail_breach = False
            if self.plan.side == "BUY" and candles[idx].get("low", 0) <= self.current_sl:
                trail_breach = True
            elif self.plan.side == "SELL" and candles[idx].get("high", 0) >= self.current_sl:
                trail_breach = True
            if trail_breach:
                self.state = TradeState.STOPPED
                r = (self.current_sl - self.plan.entry) / self.plan.risk_distance if self.plan.risk_distance and self.plan.side == "BUY" else (self.plan.entry - self.current_sl) / self.plan.risk_distance if self.plan.risk_distance else -1.0
                self.total_r += r * self.partials.remaining_ratio
                _add(TradeEvent(
                    time=str(candles[idx].get("time", "")),
                    state=TradeState.STOPPED,
                    price=self.current_sl,
                    description=f"Trailing stop hit at {self.current_sl:.2f}",
                    pnl=round(self.total_pnl, 2),
                    rr=round(self.total_r, 2),
                ))
                self.last_check_idx = idx
                return LifecycleResult(TradeState.STOPPED, new_events, done=True)

        # ── Check TP hits ──
        if self.state not in (TradeState.PENDING, TradeState.CLOSED, TradeState.STOPPED, TradeState.EXPIRED):
            tps_hit = self.fill.check_tp_hit(self.plan, candles, idx, self.last_check_idx)
            for tp_price in tps_hit:
                fraction = self.partials.hit(tp_price)
                if fraction <= 0:
                    continue

                tp_r = abs(tp_price - self.plan.entry) / self.plan.risk_distance if self.plan.risk_distance else 0
                self.total_r += tp_r * fraction
                tp_pnl = tp_r * fraction  # in R units

                # Update state
                hit_count = len(self.partials.tps_hit)
                if hit_count == 1:
                    self.state = TradeState.TP1_HIT
                elif hit_count == 2:
                    self.state = TradeState.TP2_HIT
                elif hit_count >= 3:
                    self.state = TradeState.TP3_HIT

                _add(TradeEvent(
                    time=str(candles[idx].get("time", "")),
                    state=self.state,
                    price=tp_price,
                    description=f"TP {hit_count} hit at {tp_price} (closed {fraction*100:.0f}%)",
                    pnl=round(self.total_pnl, 2),
                    rr=round(self.total_r, 2),
                ))

                # Check BE activation (after TP1)
                if hit_count == 1:
                    was_activated = self.breakeven.check_and_activate(
                        self.plan, tp_price)
                    if was_activated:
                        self.current_sl = self.breakeven.be_price
                        self.state = TradeState.BE_SET
                        _add(TradeEvent(
                            time=str(candles[idx].get("time", "")),
                            state=TradeState.BE_SET,
                            price=self.current_sl,
                            description=f"SL moved to breakeven ({self.current_sl:.2f})",
                        ))

                # Check trailing activation (after TP2)
                if hit_count == 2:
                    was_activated = self.trailing.activate(self.plan, tp_price, self.current_sl)
                    if was_activated:
                        self.state = TradeState.TRAILING
                        _add(TradeEvent(
                            time=str(candles[idx].get("time", "")),
                            state=TradeState.TRAILING,
                            price=self.trailing.current_stop,
                            description=f"Trailing stop activated at {self.trailing.current_stop:.2f}",
                        ))

            # Check if all TPs hit
            if self.partials.all_tps_hit:
                self.state = TradeState.CLOSED
                self.last_check_idx = idx
                return LifecycleResult(TradeState.CLOSED, new_events, done=True)

        self.last_check_idx = idx
        return LifecycleResult(self.state, new_events, done=False)

    # ── Execution mode: event-driven ─────────────────────────────
    def apply_broker_event(self, event_type: str, price: float,
                           timestamp: str = "") -> LifecycleResult:
        """Process a broker event (FILLED, TP_HIT, SL_HIT, EXIT).

        This is the execution-mode equivalent of step().
        The lifecycle advances state based on the event without scanning candles.

        Args:
            event_type: FILLED | TP_HIT | SL_HIT | EXIT
            price:      event price
            timestamp:  ISO timestamp

        Returns:
            LifecycleResult with new state, events, and done flag.
        """
        new_events = []
        _add = lambda ev: (self.events.append(ev), new_events.append(ev))

        if event_type == "FILLED":
            if self.state != TradeState.PENDING:
                return LifecycleResult(self.state, [], False)
            self.state = TradeState.FILLED
            self.current_sl = self.plan.stop_loss
            _add(TradeEvent(
                time=timestamp, state=TradeState.FILLED, price=price,
                description=f"Entry filled at {price} (execution)",
            ))
            return LifecycleResult(TradeState.FILLED, new_events, False)

        elif event_type == "TP_HIT":
            fraction = self.partials.hit(price)
            if fraction <= 0:
                return LifecycleResult(self.state, [], False)

            tp_r = abs(price - self.plan.entry) / self.plan.risk_distance if self.plan.risk_distance else 0
            self.total_r += tp_r * fraction
            hit_count = len(self.partials.tps_hit)

            if hit_count == 1:
                self.state = TradeState.TP1_HIT
            elif hit_count == 2:
                self.state = TradeState.TP2_HIT
            elif hit_count >= 3:
                self.state = TradeState.TP3_HIT

            _add(TradeEvent(
                time=timestamp, state=self.state, price=price,
                description=f"TP {hit_count} hit at {price} (closed {fraction*100:.0f}%)",
                rr=round(tp_r * fraction, 2),
            ))

            # BE activation after TP1
            if hit_count == 1:
                was = self.breakeven.check_and_activate(self.plan, price)
                if was:
                    self.current_sl = self.breakeven.be_price
                    self.state = TradeState.BE_SET
                    _add(TradeEvent(
                        time=timestamp, state=TradeState.BE_SET, price=self.current_sl,
                        description=f"SL moved to breakeven ({self.current_sl:.2f})",
                    ))

            # Trailing activation after TP2
            if hit_count == 2:
                was = self.trailing.activate(self.plan, price, self.current_sl)
                if was:
                    self.state = TradeState.TRAILING
                    _add(TradeEvent(
                        time=timestamp, state=TradeState.TRAILING,
                        price=self.trailing.current_stop,
                        description=f"Trailing stop activated at {self.trailing.current_stop:.2f}",
                    ))

            if self.partials.all_tps_hit:
                self.state = TradeState.CLOSED
                return LifecycleResult(TradeState.CLOSED, new_events, True)

            return LifecycleResult(self.state, new_events, False)

        elif event_type == "SL_HIT":
            if self.state in (TradeState.CLOSED, TradeState.STOPPED):
                return LifecycleResult(self.state, [], True)

            self.state = TradeState.STOPPED
            if self.plan.side == "BUY":
                r = (price - self.plan.entry) / self.plan.risk_distance if self.plan.risk_distance else -1.0
            else:
                r = (self.plan.entry - price) / self.plan.risk_distance if self.plan.risk_distance else -1.0
            self.total_r += r * self.partials.remaining_ratio

            _add(TradeEvent(
                time=timestamp, state=TradeState.STOPPED, price=price,
                description=f"Stop Loss hit at {price} (execution)",
                rr=round(self.total_r, 2),
            ))
            return LifecycleResult(TradeState.STOPPED, new_events, True)

        elif event_type == "EXIT":
            self.state = TradeState.CLOSED
            remaining = self.partials.remaining_ratio
            if remaining > 0 and self.plan.risk_distance:
                r = (price - self.plan.entry) / self.plan.risk_distance if self.plan.side == "BUY" else (self.plan.entry - price) / self.plan.risk_distance
                self.total_r += r * remaining

            _add(TradeEvent(
                time=timestamp, state=TradeState.CLOSED, price=price,
                description=f"Trade closed at {price} (manual exit)",
                rr=round(self.total_r, 2),
            ))
            return LifecycleResult(TradeState.CLOSED, new_events, True)

        return LifecycleResult(self.state, [], False)

    def _get_sl_hit_price(self, candles: List[Dict], idx: int,
                          prev_idx: int) -> Optional[float]:
        for i in range(prev_idx + 1, idx + 1):
            c = candles[i]
            if self.plan.side == "BUY" and c["low"] <= self.current_sl:
                return self.current_sl
            if self.plan.side == "SELL" and c["high"] >= self.current_sl:
                return self.current_sl
        return None
