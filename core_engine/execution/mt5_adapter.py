"""MetaTrader 5 adapter — concrete BrokerAdapter with error mapping + position tracking.

Features:
    - Full error mapping (retcodes → typed exceptions)
    - Symbol info caching
    - Position tracking for diff-based event detection (TP/SL hits)
    - Structured logging for every operation
    - Slippage and spread awareness
    - Restart recovery via get_all_positions()

Usage:
    adapter = MT5Adapter(symbol="XAUUSD", magic=202406)
    adapter.connect(login=123, password="pwd", server="ICMarkets-Demo")
    result = adapter.place_order(plan, 0.1)
    adapter.disconnect()
"""

from __future__ import annotations
import logging
import time
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field

from .broker import (
    BrokerAdapter, OrderResult, PositionInfo,
    BrokerEvent, OrderSide, OrderType,
)
from .reconnect import ReconnectManager
from .retry import retry
from .errors import (
    ConnectionError, BrokerNotConnectedError,
    OrderRejectedError, InvalidStopsError,
    InvalidVolumeError, NoMoneyError,
    MarketClosedError, TradeDisabledError,
    RequoteError, map_retcode,
)

logger = logging.getLogger(__name__)


# ── TODO check constant names for MT5 Python API without importing ──
# We import lazily; these are the standard constants.
# If the installed MetaTrader5 package differs, adjust as needed.

class _MT5Const:
    """Safe constant references — populated on first connect."""
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5

    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_SLTP = 5
    TRADE_ACTION_REMOVE = 6

    ORDER_TIME_GTC = 0
    ORDER_TIME_DAY = 1
    ORDER_TIME_SPECIFIED = 2

    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    TRADE_RETCODE_PLACED = 10008

    SYMBOL_TRADE_MODE_DISABLED = 0
    SYMBOL_TRADE_MODE_LONG = 1
    SYMBOL_TRADE_MODE_SHORT = 2
    SYMBOL_TRADE_MODE_BOTH = 3


class MT5Adapter(BrokerAdapter):
    """MT5 broker adapter with full error mapping + position tracking.

    Args:
        magic: EA magic number (identifies this bot's trades)
        max_slippage: max slippage in points (default 50)
        max_spread: max allowed spread in points (default 50)
        order_filling: ORDER_FILLING_IOC or ORDER_FILLING_RETURN
    """

    def __init__(
        self,
        login: int = 0,
        password: str = "",
        server: str = "",
        path: str = "",
        magic: int = 202406,
        max_slippage: int = 50,
        max_spread: int = 50,
        order_filling: int = 1,  # ORDER_FILLING_IOC
    ):
        self._login = login
        self._password = password
        self._server = server
        self._path = path
        self.magic = magic
        self.max_slippage = max_slippage
        self.max_spread = max_spread
        self._order_filling = order_filling

        self._mt5 = None
        self._mt = _MT5Const()
        self._connected = False
        self._symbol_info_cache: Dict[str, Any] = {}
        self._symbol_info_ts: float = 0.0
        self._known_tickets: Set[str] = set()

        self._reconnect = ReconnectManager(
            connect_fn=self._do_connect,
            disconnect_fn=self._do_disconnect,
        )

    # ── Connection ───────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect to MT5 terminal using credentials from __init__."""
        return self._reconnect.connect()

    def disconnect(self):
        self._reconnect.disconnect()

    def is_connected(self) -> bool:
        return self._reconnect.is_connected

    def _do_connect(self) -> bool:
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
        except ImportError:
            logger.error("MetaTrader5 package not installed. Run: pip install MetaTrader5")
            return False

        kwargs = {}
        if self._path:
            kwargs["path"] = self._path
        if self._login and self._password and self._server:
            kwargs["login"] = self._login
            kwargs["password"] = self._password
            kwargs["server"] = self._server

        initialized = mt5.initialize(**kwargs) if kwargs else mt5.initialize()
        if not initialized:
            error = mt5.last_error()
            logger.error("MT5 initialize() failed: %s", error)
            return False

        # Verify account
        account_info = mt5.account_info()
        if account_info:
            logger.info("MT5 connected: %s (balance=%.2f, equity=%.2f)",
                        account_info.name, account_info.balance, account_info.equity)
        else:
            logger.warning("MT5 connected but account_info() returned None")

        self._connected = True
        self._known_tickets = set()
        self._symbol_info_cache = {}
        return True

    def _do_disconnect(self):
        if self._mt5:
            try:
                self._mt5.shutdown()
            except Exception as e:
                logger.warning("MT5 shutdown error: %s", e)
        self._connected = False
        logger.info("MT5 disconnected")

    # ── Order placement ──────────────────────────────────────────

    @retry(max_attempts=3, exceptions=(OrderRejectedError, ConnectionError))
    def place_order(self, plan: "TradePlan", volume: float) -> OrderResult:
        """Place a market order from a TradePlan.

        Raises typed exceptions on failure via _check_result().
        """
        self._ensure_connected()

        mt5 = self._mt5
        mt = self._mt
        symbol = plan.label or ""

        if not symbol:
            # Discover symbol from positions or fallback
            symbol = self._guess_symbol()
            if not symbol:
                return OrderResult(False, status="NO_SYMBOL",
                                   message="No symbol in plan and cannot guess")

        # Validate symbol
        info = self._get_symbol_info(symbol)
        if info is None:
            return OrderResult(False, status="UNKNOWN_SYMBOL",
                               message=f"Symbol {symbol} not found")

        # Check spread
        spread = getattr(info, "spread", 0)
        if spread > self.max_spread:
            return OrderResult(False, status="SPREAD_TOO_HIGH",
                               message=f"Spread {spread} > max {self.max_spread}")

        # Determine price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(False, status="NO_TICK",
                               message=f"Cannot get tick for {symbol}")

        order_type = mt.ORDER_TYPE_BUY if plan.side == "BUY" else mt.ORDER_TYPE_SELL
        price = tick.ask if plan.side == "BUY" else tick.bid

        # Validate stops against symbol rules
        sl = plan.stop_loss
        tp = plan.take_profits[0] if plan.take_profits else 0
        sl = self._clamp_stop(symbol, order_type, price, sl, is_sl=True)
        tp = self._clamp_stop(symbol, order_type, price, tp, is_sl=False) if tp else 0

        request = {
            "action": mt.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": self._normalise_volume(symbol, volume),
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.max_slippage,
            "magic": self.magic,
            "comment": f"EA_{self.magic}",
            "type_time": mt.ORDER_TIME_GTC,
            "type_filling": self._order_filling,
        }

        logger.info("Order: %s %s %.2f @ %s (SL=%s TP=%s)",
                    plan.side, symbol, volume, price, sl, tp)

        result = mt5.order_send(request)
        if result is None:
            err = mt5.last_error()
            logger.error("order_send returned None: %s", err)
            raise ConnectionError(f"order_send failed: {err}")

        return self._check_result(result, symbol, plan.side, volume)

    @retry(max_attempts=2, exceptions=(ConnectionError,))
    def modify_sl(self, ticket: str, sl_price: float) -> bool:
        self._ensure_connected()
        mt5 = self._mt5
        mt = self._mt

        pos = self._get_position_by_ticket(ticket)
        if not pos:
            logger.warning("modify_sl: position %s not found", ticket)
            return False

        request = {
            "action": mt.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": int(ticket),
            "sl": sl_price,
            "tp": pos.take_profit,
        }

        logger.info("modify_sl: ticket=%s sl=%.5f (current=%.5f)",
                     ticket, sl_price, pos.stop_loss)

        result = mt5.order_send(request)
        if result is None or result.retcode != mt.TRADE_RETCODE_DONE:
            code = result.retcode if result else "NONE"
            logger.warning("modify_sl FAILED: ticket=%s retcode=%s", ticket, code)
            return False
        return True

    @retry(max_attempts=2, exceptions=(ConnectionError,))
    def modify_tp(self, ticket: str, tp_price: float) -> bool:
        self._ensure_connected()
        mt5 = self._mt5
        mt = self._mt

        pos = self._get_position_by_ticket(ticket)
        if not pos:
            logger.warning("modify_tp: position %s not found", ticket)
            return False

        request = {
            "action": mt.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": int(ticket),
            "sl": pos.stop_loss,
            "tp": tp_price,
        }

        logger.info("modify_tp: ticket=%s tp=%.5f", ticket, tp_price)

        result = mt5.order_send(request)
        if result is None or result.retcode != mt.TRADE_RETCODE_DONE:
            code = result.retcode if result else "NONE"
            logger.warning("modify_tp FAILED: ticket=%s retcode=%s", ticket, code)
            return False
        return True

    @retry(max_attempts=2, exceptions=(ConnectionError,))
    def close_position(self, ticket: str, volume: float = 0.0) -> OrderResult:
        self._ensure_connected()
        mt5 = self._mt5
        mt = self._mt

        pos = self._get_position_by_ticket(ticket)
        if not pos:
            return OrderResult(False, status="NOT_FOUND",
                               message=f"Position {ticket} not found")

        close_vol = pos.volume if volume == 0 else min(volume, pos.volume)
        close_vol = self._normalise_volume(pos.symbol, close_vol)

        order_type = mt.ORDER_TYPE_SELL if pos.side == OrderSide.BUY else mt.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if pos.side == OrderSide.BUY else tick.ask

        request = {
            "action": mt.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": close_vol,
            "type": order_type,
            "position": int(ticket),
            "price": price,
            "deviation": self.max_slippage,
            "magic": self.magic,
            "comment": f"Close_{ticket}",
            "type_time": mt.ORDER_TIME_GTC,
            "type_filling": mt.ORDER_FILLING_IOC,
        }

        logger.info("Close: ticket=%s vol=%s price=%.5f", ticket, close_vol, price)

        result = mt5.order_send(request)
        if result is None:
            return OrderResult(False, status="ERROR",
                               message=f"close_position returned None: {mt5.last_error()}")

        if result.retcode == mt.TRADE_RETCODE_DONE:
            return OrderResult(True, order_id=ticket,
                               filled_price=result.price,
                               filled_volume=close_vol, status="CLOSED")
        else:
            exc = map_retcode(result.retcode, f"Close {ticket}: {result.comment}")
            return OrderResult(False, status=f"RETCODE_{result.retcode}",
                               message=str(exc))

    # ── Position queries ─────────────────────────────────────────

    def get_position(self, ticket: str) -> Optional[PositionInfo]:
        self._ensure_connected()
        return self._get_position_by_ticket(ticket)

    def get_all_positions(self) -> List[PositionInfo]:
        self._ensure_connected()
        mt5 = self._mt5
        positions = mt5.positions_get()
        if not positions:
            return []
        return [self._mt5_pos_to_info(p) for p in positions]

    # ── Event polling ────────────────────────────────────────────

    def poll_events(self) -> List[BrokerEvent]:
        """Detect position changes since last poll.

        Detects:
            - Closed positions (disappeared from open list)
            - New fills (appeared in open list)
            - TP/SL hits via trade history lookup

        On first call, registers all open positions as "known".
        """
        self._ensure_connected()
        events: List[BrokerEvent] = []
        current = self.get_all_positions()
        current_tickets = {p.ticket for p in current}

        # First call: just register all open as known
        if not self._known_tickets:
            self._known_tickets = current_tickets
            logger.info("poll_events: registered %d known positions", len(self._known_tickets))
            return events

        # Check if any known ticket disappeared (closed)
        now_ts = int(time.time())
        for ticket in list(self._known_tickets):
            if ticket not in current_tickets:
                # Look up how it closed via trade history
                event = self._lookup_close_event(ticket, now_ts)
                events.append(event)
                self._known_tickets.discard(ticket)

        # Detect new positions
        for ticket in current_tickets:
            if ticket not in self._known_tickets:
                pos = next((p for p in current if p.ticket == ticket), None)
                if pos:
                    events.append(BrokerEvent(
                        type="FILLED", ticket=ticket,
                        price=pos.open_price, volume=pos.volume,
                        time=str(now_ts),
                    ))
                    self._known_tickets.add(ticket)

        return events

    def _lookup_close_event(self, ticket: str, around_ts: int) -> BrokerEvent:
        """Look up how a position was closed via MT5 trade history.

        Checks the last 60s of history for a deal matching the ticket.
        Falls back to CLOSED if history not available.
        """
        mt5 = self._mt5
        try:
            # Check history from 3600s ago to now
            from_ts = around_ts - 3600
            to_ts = around_ts + 60
            history = mt5.history_deals_get(from_ts, to_ts)
            if history:
                for deal in history:
                    d_ticket = getattr(deal, "position_id", None) or getattr(deal, "order", 0)
                    if str(d_ticket) == ticket:
                        profit = getattr(deal, "profit", 0)
                        price = getattr(deal, "price", 0.0)
                        reason = getattr(deal, "reason", 0)
                        # reason=3 (TP), reason=4 (SL)
                        if reason == 3:
                            return BrokerEvent(
                                type="TP_HIT", ticket=ticket, price=price,
                                time=str(getattr(deal, "time", "")),
                            )
                        elif reason == 4:
                            return BrokerEvent(
                                type="SL_HIT", ticket=ticket, price=price,
                                time=str(getattr(deal, "time", "")),
                            )
                        else:
                            return BrokerEvent(
                                type="CLOSED", ticket=ticket, price=price,
                                time=str(getattr(deal, "time", "")),
                                extra={"reason": "manual", "profit": profit},
                            )
        except Exception as e:
            logger.debug("Trade history lookup failed for %s: %s", ticket, e)

        # Fallback: treat as manual close
        return BrokerEvent(
            type="CLOSED", ticket=ticket, price=0.0,
            time=str(around_ts),
            extra={"reason": "unknown"},
        )

    # ── Account ──────────────────────────────────────────────────

    def get_account_balance(self) -> float:
        self._ensure_connected()
        info = self._mt5.account_info()
        return info.balance if info else 0.0

    def get_account_equity(self) -> float:
        self._ensure_connected()
        info = self._mt5.account_info()
        return info.equity if info else 0.0

    # ── Symbol info ──────────────────────────────────────────────

    def get_symbol_info(self, symbol: str):
        """Get cached symbol info."""
        return self._get_symbol_info(symbol)

    # ── Internal: error checking ─────────────────────────────────

    def _check_result(self, result, symbol: str, side: str,
                      volume: float) -> OrderResult:
        """Convert MT5 trade result to OrderResult with error mapping."""
        mt = self._mt

        if result.retcode == mt.TRADE_RETCODE_DONE:
            logger.info("FILLED: %s %s @ %.5f vol=%s ticket=%s",
                         side, symbol, result.price, result.volume, result.order)
            return OrderResult(
                success=True,
                order_id=str(result.order),
                filled_price=result.price,
                filled_volume=result.volume,
                status="FILLED",
            )

        if result.retcode == mt.TRADE_RETCODE_DONE_PARTIAL:
            logger.warning("PARTIAL FILL: %s %s @ %.5f vol=%s ticket=%s",
                            side, symbol, result.price, result.volume, result.order)
            return OrderResult(
                success=True,
                order_id=str(result.order),
                filled_price=result.price,
                filled_volume=result.volume,
                status="PARTIAL",
            )

        if result.retcode == mt.TRADE_RETCODE_PLACED:
            logger.info("ORDER PLACED (pending): %s %s @ %.5f",
                         side, symbol, result.price)
            return OrderResult(
                success=True,
                order_id=str(result.order),
                filled_price=result.price,
                filled_volume=result.volume,
                status="PENDING",
            )

        # Error — raise typed exception
        exc = map_retcode(result.retcode,
                          f"{side} {symbol} vol={volume}: {result.comment}")
        logger.error("ORDER REJECTED: %s %s — %s", side, symbol, exc)
        raise exc

    # ── Internal: helpers ────────────────────────────────────────

    def _ensure_connected(self):
        if not self._reconnect.ensure_connected():
            raise BrokerNotConnectedError("MT5 not connected")

    def _get_position_by_ticket(self, ticket: str) -> Optional[PositionInfo]:
        mt5 = self._mt5
        try:
            positions = mt5.positions_get(ticket=int(ticket))
            if not positions or len(positions) == 0:
                return None
            return self._mt5_pos_to_info(positions[0])
        except Exception as e:
            logger.warning("positions_get(%s) error: %s", ticket, e)
            return None

    def _mt5_pos_to_info(self, p) -> PositionInfo:
        mt = self._mt
        side = OrderSide.BUY if p.type == mt.ORDER_TYPE_BUY else OrderSide.SELL
        return PositionInfo(
            ticket=str(p.ticket),
            symbol=p.symbol,
            side=side,
            volume=p.volume,
            open_price=p.price_open,
            stop_loss=p.sl,
            take_profit=p.tp,
            profit=p.profit,
            swap=p.swap if hasattr(p, 'swap') else 0.0,
        )

    def _get_symbol_info(self, symbol: str):
        """Cached symbol info lookup."""
        now = time.time()
        if symbol in self._symbol_info_cache and now - self._symbol_info_ts < 30:
            return self._symbol_info_cache[symbol]

        try:
            info = self._mt5.symbol_info(symbol)
            if info:
                self._symbol_info_cache[symbol] = info
                self._symbol_info_ts = now
            return info
        except Exception:
            return None

    def _normalise_volume(self, symbol: str, volume: float) -> float:
        """Round volume to symbol step."""
        try:
            info = self._get_symbol_info(symbol)
            if info and hasattr(info, 'volume_step') and info.volume_step > 0:
                step = info.volume_step
                return round(round(volume / step) * step, 4)
        except Exception:
            pass
        return round(volume, 2)

    def _clamp_stop(self, symbol: str, order_type: int, price: float,
                    stop_price: float, is_sl: bool) -> float:
        """Clamp SL/TP to minimum distance from entry if broker requires it."""
        try:
            info = self._get_symbol_info(symbol)
            if not info:
                return stop_price

            is_buy = order_type == self._mt.ORDER_TYPE_BUY
            label = "SL" if is_sl else "TP"
            _ = label  # used in debug

            # MT5 provides min/max distance in points
            if is_sl:
                if is_buy:
                    min_dist = getattr(info, "stops_level", 0) * getattr(info, "point", 0)
                    if min_dist > 0 and stop_price > price - min_dist:
                        stop_price = price - min_dist
                else:
                    min_dist = getattr(info, "stops_level", 0) * getattr(info, "point", 0)
                    if min_dist > 0 and stop_price < price + min_dist:
                        stop_price = price + min_dist
        except Exception:
            pass
        return stop_price

    def _guess_symbol(self) -> str:
        """Guess symbol from existing positions or account info."""
        try:
            positions = self._mt5.positions_get()
            if positions and len(positions) > 0:
                return positions[0].symbol
        except Exception:
            pass
        return ""
