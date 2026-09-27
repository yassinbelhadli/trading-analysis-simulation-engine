from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import MetaTrader5 as mt5
import numpy as np

from core_engine.mt_runtime import (
    MTRuntime,
    MTConnectionConfig,
    MTAccountInfo,
    MTSymbolInfo,
    MTPosition,
    MTOrder,
    MTTick,
    MTRuntimeError,
    get_attr,
)

logger = logging.getLogger(__name__)

MINUTES_TO_MT5_TF: Dict[int, int] = {
    1: mt5.TIMEFRAME_M1,
    2: mt5.TIMEFRAME_M2,
    3: mt5.TIMEFRAME_M3,
    4: mt5.TIMEFRAME_M4,
    5: mt5.TIMEFRAME_M5,
    6: mt5.TIMEFRAME_M6,
    10: mt5.TIMEFRAME_M10,
    12: mt5.TIMEFRAME_M12,
    15: mt5.TIMEFRAME_M15,
    20: mt5.TIMEFRAME_M20,
    30: mt5.TIMEFRAME_M30,
    60: mt5.TIMEFRAME_H1,
    120: mt5.TIMEFRAME_H2,
    180: mt5.TIMEFRAME_H3,
    240: mt5.TIMEFRAME_H4,
    360: mt5.TIMEFRAME_H6,
    480: mt5.TIMEFRAME_H8,
    720: mt5.TIMEFRAME_H12,
    1440: mt5.TIMEFRAME_D1,
    10080: mt5.TIMEFRAME_W1,
    43200: mt5.TIMEFRAME_MN1,
}

POSITION_TYPE_MAP = {0: "BUY", 1: "SELL"}


def _mt5_timeframe(minutes: int) -> int:
    return MINUTES_TO_MT5_TF.get(minutes, mt5.TIMEFRAME_M5)


class MT5Runtime(MTRuntime):
    def __init__(self, config: MTConnectionConfig):
        super().__init__(config)
        self._path: Optional[str] = None

    async def connect(self) -> bool:
        kwargs = {
            "login": int(self.config.login),
            "server": self.config.server,
            "password": self.config.password,
            # MT5 natively aborts initialize() after this many ms; without it a
            # stuck terminal/unreachable server hangs forever and each timed-out
            # connect leaks a thread blocked on the module's internal lock.
            "timeout": 10000,
        }
        if self.config.platform.upper() == "MT5":
            kwargs["path"] = r"C:\Program Files\MetaTrader 5\terminal64.exe"

        # mt5.initialize() can block for a long time when the terminal/server is
        # unreachable. Run it in a worker thread so a caller-side timeout can
        # give up instead of freezing the event loop.
        initialized = await asyncio.to_thread(mt5.initialize, **kwargs)
        if not initialized:
            error = mt5.last_error()
            logger.error("MT5 initialize failed: %s", error)
            self._connected = False
            return False

        info = mt5.terminal_info()
        if info:
            logger.info("MT5 connected: %s %s", info.name, info.path)

        self._connected = True
        return True

    async def disconnect(self) -> None:
        mt5.shutdown()
        self._connected = False
        logger.info("MT5 disconnected")

    async def account_info(self) -> MTAccountInfo:
        self._require_connected()
        info = mt5.account_info()
        if info is None:
            raise MTRuntimeError("Failed to get account info")
        return MTAccountInfo(
            login=info.login,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            margin_free=info.margin_free,
            margin_level=info.margin_level,
            leverage=info.leverage,
            currency=info.currency,
            server=info.server,
            name=info.name,
            company=info.company,
            is_demo=info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO,
            trade_mode=info.trade_mode,
            connected=self._connected,
        )

    async def get_symbols(self) -> List[MTSymbolInfo]:
        self._require_connected()
        symbols = mt5.symbols_get()
        if symbols is None:
            return []
        result = []
        for s in symbols:
            result.append(MTSymbolInfo(
                name=s.name,
                digits=s.digits,
                spread=s.spread,
                swap_long=s.swap_long,
                swap_short=s.swap_short,
                min_volume=s.volume_min,
                max_volume=s.volume_max,
                volume_step=s.volume_step,
                bid=s.bid,
                ask=s.ask,
                point=s.point,
                tick_value=s.trade_tick_value,
                tick_size=s.trade_tick_size,
                contract_size=get_attr(s, "trade_contract_size", "contract_size", default=0.0),
                trade_mode=s.trade_mode,
            ))
        return result

    async def get_rates(self, symbol: str, timeframe: int, count: int = 100) -> List[Dict]:
        self._require_connected()
        mt5_tf = _mt5_timeframe(timeframe)
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        if rates is None:
            return []
        return [
            {
                "time": datetime.fromtimestamp(r[0]),
                "open": r[1],
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "tick_volume": r[5],
                "spread": r[6],
                "real_volume": r[7],
            }
            for r in rates
        ]

    async def get_ticks(self, symbol: str, count: int = 10) -> List[MTTick]:
        self._require_connected()
        ticks = mt5.copy_ticks_from(symbol, datetime.now(), count, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            return []
        return [
            MTTick(
                symbol=symbol,
                bid=t[1],
                ask=t[2],
                last=t[3],
                volume=int(t[4]),
                time=datetime.fromtimestamp(t[0]),
            )
            for t in ticks[:count]
        ]

    async def get_positions(self) -> List[MTPosition]:
        self._require_connected()
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [
            MTPosition(
                ticket=p.ticket,
                symbol=p.symbol,
                type=p.type,
                volume=p.volume,
                open_price=p.price_open,
                current_price=p.price_current,
                stop_loss=p.sl,
                take_profit=p.tp,
                profit=p.profit,
                swap=p.swap,
                comment=p.comment,
                open_time=datetime.fromtimestamp(p.time),
            )
            for p in positions
        ]

    async def get_orders(self) -> List[MTOrder]:
        self._require_connected()
        orders = mt5.orders_get()
        if orders is None:
            return []
        return [
            MTOrder(
                ticket=o.ticket,
                symbol=o.symbol,
                type=o.type,
                volume=o.volume_current,
                price=o.price_open,
                stop_loss=o.sl,
                take_profit=o.tp,
                comment=o.comment,
                open_time=datetime.fromtimestamp(o.time_setup),
                expiration=datetime.fromtimestamp(o.time_expiration) if o.time_expiration else None,
            )
            for o in orders
        ]

    async def place_order(
        self,
        symbol: str,
        order_type: int,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        comment: str = "",
    ) -> int:
        self._require_connected()
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 202507,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = mt5.last_error()
            logger.error("place_order failed for %s: retcode=%s, error=%s",
                         symbol, result.retcode if result else "NONE", error)
            raise MTRuntimeError(
                f"Order failed: {result.comment if result else 'No response'}"
            )
        return result.order

    async def cancel_order(self, ticket: int) -> bool:
        self._require_connected()
        orders = mt5.orders_get()
        if orders is None:
            return False
        target = [o for o in orders if o.ticket == ticket]
        if not target:
            return False
        order = target[0]
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    async def modify_sl(self, ticket: int, sl: float) -> bool:
        self._require_connected()
        positions = mt5.positions_get()
        if positions is None:
            return False
        target = [p for p in positions if p.ticket == ticket]
        if not target:
            return False
        pos = target[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": pos.symbol,
            "sl": sl,
            "tp": pos.tp,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    async def partial_close(self, ticket: int, volume: float) -> bool:
        self._require_connected()
        positions = mt5.positions_get()
        if positions is None:
            return False
        target = [p for p in positions if p.ticket == ticket]
        if not target:
            return False
        pos = target[0]
        close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": volume,
            "type": close_type,
            "position": ticket,
            "price": pos.price_current,
            "deviation": 20,
            "magic": 202507,
            "comment": "partial_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def _require_connected(self):
        if not self._connected:
            raise MTRuntimeError("MT5 not connected")
