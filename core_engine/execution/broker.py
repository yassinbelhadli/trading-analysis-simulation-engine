"""Broker Adapter — abstract interface + PaperBroker for testing.

The adapter abstracts all broker-specific operations behind a uniform interface.
To add a new broker (MT5, cTrader, Binance), implement this interface.
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from ..simulation.planner import TradePlan

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    _MT5_AVAILABLE = False


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class OrderResult:
    """Result of placing an order with the broker."""
    success: bool
    order_id: str = ""
    filled_price: float = 0.0
    filled_volume: float = 0.0
    status: str = ""         # FILLED, PARTIAL, PENDING, REJECTED
    message: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionInfo:
    """Current state of an open position."""
    ticket: str
    symbol: str
    side: OrderSide
    volume: float
    open_price: float
    stop_loss: float
    take_profit: float
    profit: float
    swap: float = 0.0


@dataclass
class BrokerEvent:
    """Event emitted by the broker (fill, TP/SL hit, etc.)."""
    type: str              # FILLED | TP_HIT | SL_HIT | MODIFIED | CLOSED
    ticket: str
    price: float
    volume: float = 0.0
    time: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


class BrokerAdapter(ABC):
    """Abstract broker interface.

    All broker implementations (MT5, cTrader, Binance) implement this.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker."""

    @abstractmethod
    def disconnect(self):
        """Disconnect from broker."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""

    @abstractmethod
    def place_order(self, plan: TradePlan, volume: float) -> OrderResult:
        """Place a new order from a TradePlan.

        Args:
            plan: TradePlan with entry, SL, TP
            volume: lot/unit size

        Returns:
            OrderResult with fill details
        """

    @abstractmethod
    def modify_sl(self, ticket: str, sl_price: float) -> bool:
        """Modify stop loss on an existing position."""

    @abstractmethod
    def modify_tp(self, ticket: str, tp_price: float) -> bool:
        """Modify take profit on an existing position."""

    @abstractmethod
    def close_position(self, ticket: str, volume: float = 0.0) -> OrderResult:
        """Close a position (volume=0 means full close)."""

    @abstractmethod
    def get_position(self, ticket: str) -> Optional[PositionInfo]:
        """Get current position details."""

    @abstractmethod
    def get_all_positions(self) -> List[PositionInfo]:
        """Get all open positions."""

    @abstractmethod
    def poll_events(self) -> List[BrokerEvent]:
        """Poll for new broker events since last call.

        Returns:
            List of BrokerEvent (FILLED, TP_HIT, SL_HIT, CLOSED).
        """

    @abstractmethod
    def get_account_balance(self) -> float:
        """Get current account balance."""


# ── PaperBroker (in-memory, for testing) ─────────────────────────

class PaperBroker(BrokerAdapter):
    """In-memory broker for testing execution without real connection.

    Simulates fills, SL/TP hits, and emits BrokerEvents.
    """

    def __init__(self, balance: float = 10000.0, slippage: float = 0.0005):
        self._balance = balance
        self._slippage = slippage
        self._connected = True
        self._positions: Dict[str, PositionInfo] = {}
        self._next_ticket = 1000
        self._events: List[BrokerEvent] = []

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def place_order(self, plan: TradePlan, volume: float) -> OrderResult:
        if not self._connected:
            return OrderResult(False, status="NOT_CONNECTED", message="Broker not connected")

        slippage = plan.entry * self._slippage
        if plan.side == "BUY":
            fill_price = plan.entry + slippage
        else:
            fill_price = plan.entry - slippage

        ticket = str(self._next_ticket)
        self._next_ticket += 1

        side = OrderSide.BUY if plan.side == "BUY" else OrderSide.SELL
        pos = PositionInfo(
            ticket=ticket,
            symbol=plan.label or "PAPER",
            side=side,
            volume=volume,
            open_price=round(fill_price, 2),
            stop_loss=plan.stop_loss,
            take_profit=plan.take_profits[0] if plan.take_profits else 0,
            profit=0,
        )
        self._positions[ticket] = pos

        self._events.append(BrokerEvent(
            type="FILLED",
            ticket=ticket,
            price=round(fill_price, 2),
            volume=volume,
            extra={"plan_side": plan.side, "entry": plan.entry},
        ))

        return OrderResult(
            success=True,
            order_id=ticket,
            filled_price=round(fill_price, 2),
            filled_volume=volume,
            status="FILLED",
            extra={"position": pos},
        )

    def modify_sl(self, ticket: str, sl_price: float) -> bool:
        pos = self._positions.get(ticket)
        if not pos:
            return False
        pos.stop_loss = sl_price
        self._events.append(BrokerEvent(
            type="MODIFIED", ticket=ticket, price=sl_price,
            extra={"field": "SL"},
        ))
        return True

    def modify_tp(self, ticket: str, tp_price: float) -> bool:
        pos = self._positions.get(ticket)
        if not pos:
            return False
        pos.take_profit = tp_price
        self._events.append(BrokerEvent(
            type="MODIFIED", ticket=ticket, price=tp_price,
            extra={"field": "TP"},
        ))
        return True

    def close_position(self, ticket: str, volume: float = 0.0) -> OrderResult:
        pos = self._positions.get(ticket)
        if not pos:
            return OrderResult(False, status="NOT_FOUND", message="Position not found")

        close_vol = pos.volume if volume == 0 else min(volume, pos.volume)
        self._events.append(BrokerEvent(
            type="CLOSED",
            ticket=ticket,
            price=pos.open_price,
            volume=close_vol,
        ))
        return OrderResult(True, order_id=ticket,
                           filled_price=pos.open_price,
                           filled_volume=close_vol,
                           status="CLOSED")

    def get_position(self, ticket: str) -> Optional[PositionInfo]:
        return self._positions.get(ticket)

    def get_all_positions(self) -> List[PositionInfo]:
        return list(self._positions.values())

    def poll_events(self) -> List[BrokerEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def get_account_balance(self) -> float:
        return self._balance

    def inject_tp_hit(self, ticket: str, tp_price: float):
        """Simulate a TP hit (for testing)."""
        self._events.append(BrokerEvent(
            type="TP_HIT", ticket=ticket, price=tp_price,
        ))

    def inject_sl_hit(self, ticket: str, sl_price: float):
        """Simulate an SL hit (for testing)."""
        self._events.append(BrokerEvent(
            type="SL_HIT", ticket=ticket, price=sl_price,
        ))


# ── MT5Broker (real execution via MT5 Python API) ─────────────────

class MT5Broker(BrokerAdapter):
    """Real broker adapter for MetaTrader 5.

    Delegates order placement, modification, and position management
    to the MT5 Python API via an MT5Runtime.
    """

    def __init__(self, runtime=None):
        if not _MT5_AVAILABLE:
            raise RuntimeError("MetaTrader5 package not installed")
        self._runtime = runtime
        self._events: List[BrokerEvent] = []
        self._last_poll_tickets: set = set()

    def _ensure_mt5_initialized(self) -> bool:
        return mt5.terminal_info() is not None

    def connect(self) -> bool:
        return self._ensure_mt5_initialized()

    def disconnect(self):
        pass

    def is_connected(self) -> bool:
        return mt5.terminal_info() is not None

    def place_order(self, plan: TradePlan, volume: float) -> OrderResult:
        try:
            _side_map = {"BUY": mt5.ORDER_TYPE_BUY, "SELL": mt5.ORDER_TYPE_SELL}
            side = _side_map.get(plan.side)
            if side is None:
                return OrderResult(False, status="REJECTED",
                                   message=f"Unknown side: {plan.side}")

            tick = mt5.symbol_info_tick(plan.label or "XAUUSD")
            if tick is None:
                return OrderResult(False, status="REJECTED",
                                   message=f"No tick for {plan.label}")

            price = tick.ask if side == mt5.ORDER_TYPE_BUY else tick.bid
            sl = plan.stop_loss or 0
            tp = plan.take_profits[0] if plan.take_profits else 0

            mt5_volume = round(volume / 100, 2)  # units → lots (1 lot = 100 units)
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": plan.label or "XAUUSD",
                "volume": mt5_volume,
                "type": side,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 123456,
                "comment": plan.label or "ICT EA",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            logger.info("MT5Broker place_order | symbol=%s side=%s vol=%s price=%s sl=%s tp=%s",
                        plan.label, plan.side, round(volume, 2), price, sl, tp)
            result = mt5.order_send(request)
            logger.info("MT5Broker result | retcode=%s comment=%s", result.retcode, result.comment)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(
                    False, status="REJECTED",
                    message=f"MT5 error {result.retcode}: {result.comment}",
                )

            ticket = str(result.order)
            self._events.append(BrokerEvent(
                type="FILLED", ticket=ticket, price=price, volume=volume,
            ))

            return OrderResult(
                success=True, order_id=ticket, filled_price=price,
                filled_volume=volume, status="FILLED",
            )

        except Exception as e:
            logger.exception("MT5Broker.place_order failed")
            return OrderResult(False, status="ERROR", message=str(e))

    def modify_sl(self, ticket: str, sl_price: float) -> bool:
        try:
            position = mt5.positions_get(ticket=int(ticket))
            if not position:
                return False
            pos = position[0]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": int(ticket),
                "symbol": pos.symbol,
                "sl": sl_price,
                "tp": pos.tp,
            }
            result = mt5.order_send(request)
            return result.retcode == mt5.TRADE_RETCODE_DONE
        except Exception:
            return False

    def modify_tp(self, ticket: str, tp_price: float) -> bool:
        try:
            position = mt5.positions_get(ticket=int(ticket))
            if not position:
                return False
            pos = position[0]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": int(ticket),
                "symbol": pos.symbol,
                "sl": pos.sl,
                "tp": tp_price,
            }
            result = mt5.order_send(request)
            return result.retcode == mt5.TRADE_RETCODE_DONE
        except Exception:
            return False

    def close_position(self, ticket: str, volume: float = 0.0) -> OrderResult:
        try:
            position = mt5.positions_get(ticket=int(ticket))
            if not position:
                return OrderResult(False, status="NOT_FOUND",
                                   message="Position not found")
            pos = position[0]
            close_vol = pos.volume if volume == 0 else min(volume, pos.volume)
            _close_map = {"BUY": mt5.ORDER_TYPE_SELL, "SELL": mt5.ORDER_TYPE_BUY}
            close_side = _close_map.get(
                "BUY" if pos.type == 0 else "SELL"
            )
            tick = mt5.symbol_info_tick(pos.symbol)
            price = tick.bid if close_side == mt5.ORDER_TYPE_SELL else tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": close_vol,
                "type": close_side,
                "position": int(ticket),
                "price": price,
                "deviation": 20,
                "magic": 123456,
                "comment": "Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(False, status="REJECTED",
                                   message=f"Close failed: {result.comment}")
            return OrderResult(True, order_id=ticket, filled_price=price,
                               filled_volume=close_vol, status="CLOSED")
        except Exception as e:
            return OrderResult(False, status="ERROR", message=str(e))

    def get_position(self, ticket: str) -> Optional[PositionInfo]:
        try:
            pos = mt5.positions_get(ticket=int(ticket))
            if not pos:
                return None
            p = pos[0]
            return PositionInfo(
                ticket=str(p.ticket),
                symbol=p.symbol,
                side=OrderSide.BUY if p.type == 0 else OrderSide.SELL,
                volume=p.volume,
                open_price=p.price_open,
                stop_loss=p.sl,
                take_profit=p.tp,
                profit=p.profit,
                swap=p.swap,
            )
        except Exception:
            return None

    def get_all_positions(self) -> List[PositionInfo]:
        try:
            positions = mt5.positions_get()
            if not positions:
                return []
            result = []
            for p in positions:
                result.append(PositionInfo(
                    ticket=str(p.ticket),
                    symbol=p.symbol,
                    side=OrderSide.BUY if p.type == 0 else OrderSide.SELL,
                    volume=p.volume,
                    open_price=p.price_open,
                    stop_loss=p.sl,
                    take_profit=p.tp,
                    profit=p.profit,
                    swap=p.swap,
                ))
            return result
        except Exception:
            return []

    def poll_events(self) -> List[BrokerEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def get_account_balance(self) -> float:
        try:
            acc = mt5.account_info()
            return acc.balance if acc else 0.0
        except Exception:
            return 0.0
