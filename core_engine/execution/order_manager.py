"""Order Manager — bridges TradePlan → Broker → Trade Lifecycle.

Dual interface:
    Framework A (execution_engine):  async place_order(plan) → OrderResult
    Framework B (broker-adapter):    submit(plan) → ticket string, poll() → closed tickets

Both paths flow through the same simulation TradeLifecycle state machine.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..simulation.planner import TradePlan
from ..simulation.lifecycle import TradeLifecycle
from ..simulation.result import TradeResult, TradeEvent, TradeOutcome
from ..simulation.risk import compute_position

from .broker import BrokerAdapter, PaperBroker, OrderResult, OrderSide
from .errors import OrderRejectedError, ExecutionError

logger = logging.getLogger(__name__)


@dataclass
class ManagedTrade:
    """A trade being managed by the OrderManager."""
    ticket: str
    plan: TradePlan
    lifecycle: TradeLifecycle
    volume: float
    symbol: str = ""
    status: str = "PENDING"


class OrderManager:
    """Manages order placement and lifecycle via a BrokerAdapter.

    Can be constructed with either:
        - BrokerAdapter (Framework B): submit/poll pattern
        - runtime object  (Framework A): async place_order(plan) pattern
    """

    def __init__(self, broker_or_runtime=None, account_balance: float = 10000.0):
        self._broker: Optional[BrokerAdapter] = None
        self._runtime = None

        if broker_or_runtime is not None:
            if isinstance(broker_or_runtime, BrokerAdapter):
                self._broker = broker_or_runtime
            else:
                self._runtime = broker_or_runtime

        if self._broker is None:
            self._broker = PaperBroker()

        self._balance = account_balance
        self._trades: Dict[str, ManagedTrade] = {}
        self._results: Dict[str, TradeResult] = {}

    # ── Framework A: async place_order (used by execution_engine.py) ──

    async def place_order(self, plan: TradePlan) -> OrderResult:
        """Place an order from a TradePlan (async, Framework A compatible).

        Args:
            plan: TradePlan with entry, SL, TPs, volume, etc.

        Returns:
            OrderResult with fill details.
        """
        try:
            ticket = self.submit(plan)
            mt = self._trades.get(ticket)
            if not mt:
                return OrderResult(False, status="ERROR", message="Trade not tracked")

            return OrderResult(
                success=True,
                order_id=ticket,
                filled_price=plan.entry_price,
                filled_volume=mt.volume,
                status="FILLED",
            )
        except OrderRejectedError as e:
            return OrderResult(False, status="REJECTED", message=str(e))
        except Exception as e:
            logger.exception("place_order failed")
            return OrderResult(False, status="ERROR", message=str(e))

    # ── Framework B: submit/poll pattern ──

    def submit(self, plan: TradePlan, account_balance: float = None) -> str:
        """Submit a TradePlan for execution.

        Returns:
            ticket string

        Raises:
            OrderRejectedError if broker rejects.
        """
        balance = account_balance or self._balance

        # Position sizing
        from ..simulation.risk import compute_position as _cp
        # Use plan's risk_distance if present, otherwise compute
        if hasattr(plan, 'entry_price') and plan.entry_price:
            risk_dist = abs(plan.entry_price - plan.stop_loss) if plan.stop_loss else 0
        else:
            risk_dist = plan.risk_distance if hasattr(plan, 'risk_distance') else 0

        vol = 0.01
        if risk_dist > 0 and balance > 0:
            pos_size = _cp(plan, balance)
            vol = pos_size.units if pos_size and pos_size.units > 0 else vol

        # Map TradePlan to broker-compatible format
        broker_plan = self._plan_to_broker(plan)

        result = self._broker.place_order(broker_plan, vol)
        if not result.success:
            raise OrderRejectedError(
                f"Order rejected: {result.message} (status={result.status})"
            )

        lc = TradeLifecycle(broker_plan)
        lc.apply_broker_event("FILLED", result.filled_price)

        ticket = result.order_id
        self._trades[ticket] = ManagedTrade(
            ticket=ticket,
            plan=broker_plan,
            lifecycle=lc,
            volume=vol,
            status="ACTIVE",
        )
        logger.info("Trade submitted: %s %s @ %s (ticket=%s, vol=%.2f)",
                    getattr(plan, 'side', '?'), getattr(plan, 'label', ''),
                    getattr(plan, 'entry_price', 0) or plan.entry, ticket, vol)
        return ticket

    def poll(self) -> List[str]:
        """Poll broker for events and update lifecycles.

        Returns:
            List of closed ticket strings.
        """
        closed = []
        events = self._broker.poll_events()
        for ev in events:
            ticket = ev.ticket
            trade = self._trades.get(ticket)
            if not trade or trade.status == "CLOSED":
                continue

            lc = trade.lifecycle

            if ev.type in ("TP_HIT",):
                lc.apply_broker_event("TP_HIT", ev.price, ev.time)
                if lc.state == "CLOSED" or lc.partials.all_tps_hit:
                    self._finalize(ticket, lc)
                    closed.append(ticket)
                else:
                    self._sync_broker(trade)

            elif ev.type == "SL_HIT":
                lc.apply_broker_event("SL_HIT", ev.price, ev.time)
                self._finalize(ticket, lc)
                closed.append(ticket)

            elif ev.type == "CLOSED":
                lc.apply_broker_event("EXIT", ev.price, ev.time)
                self._finalize(ticket, lc)
                closed.append(ticket)

        return closed

    def result(self, ticket: str) -> Optional[TradeResult]:
        """Get TradeResult for a completed trade."""
        return self._results.get(ticket)

    def active_trades(self) -> List[ManagedTrade]:
        return [t for t in self._trades.values() if t.status == "ACTIVE"]

    def close(self, ticket: str) -> bool:
        """Manually close a trade."""
        trade = self._trades.get(ticket)
        if not trade or trade.status == "CLOSED":
            return False
        result = self._broker.close_position(ticket)
        if result.success:
            trade.lifecycle.apply_broker_event("EXIT", result.filled_price)
            self._finalize(ticket, trade.lifecycle)
            return True
        return False

    # ── Internal helpers ──

    def _finalize(self, ticket: str, lc: TradeLifecycle):
        trade = self._trades.get(ticket)
        if not trade:
            return
        trade.status = "CLOSED"

        from ..simulation.engine import _determine_outcome, _clean_events
        outcome = _determine_outcome(lc.state, lc.total_r)
        events = _clean_events(lc.events)

        result = TradeResult(
            outcome=outcome,
            total_r=round(lc.total_r, 2),
            total_pnl=round(lc.total_pnl, 2),
            events=events,
            plan_id=ticket,
        )
        self._results[ticket] = result
        logger.info("Trade %s closed: %s %.2fR", ticket, outcome, lc.total_r)

    def _sync_broker(self, trade: ManagedTrade):
        """Sync SL/TP levels from lifecycle state back to broker."""
        if trade.lifecycle.state in ("BE_SET", "TRAILING"):
            self._broker.modify_sl(trade.ticket, trade.lifecycle.current_sl)

    def _plan_to_broker(self, plan: TradePlan):
        """Convert TradePlan (Framework A) to TradePlan (simulation format)."""
        # Already a simulation TradePlan if it has 'side' attr
        if hasattr(plan, 'side') and hasattr(plan, 'entry'):
            return plan

        # Map from Framework A TradePlan attributes
        from ..simulation.planner import TradePlan as SimPlan
        return SimPlan(
            entry=getattr(plan, 'entry_price', 0),
            stop_loss=getattr(plan, 'stop_loss', 0),
            take_profits=[getattr(plan, 'take_profit', 0)] if getattr(plan, 'take_profit', 0) else [],
            side=getattr(plan, 'direction', 'BUY'),
            risk_percent=getattr(plan, 'risk_percent', 0.5) or 0.5,
            partials=[1.0],
            label=getattr(plan, 'symbol', ''),
        )
