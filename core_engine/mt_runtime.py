from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class MTConnectionConfig:
    server: str
    login: str
    password: str
    platform: str  # MT4 or MT5


@dataclass
class MTAccountInfo:
    login: int
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    leverage: int
    currency: str
    server: str
    name: str
    company: str
    is_demo: bool
    trade_mode: int
    connected: bool


@dataclass
class MTPosition:
    ticket: int
    symbol: str
    type: int
    volume: float
    open_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    profit: float
    swap: float
    comment: str
    open_time: datetime


@dataclass
class MTOrder:
    ticket: int
    symbol: str
    type: int
    volume: float
    price: float
    stop_loss: float
    take_profit: float
    comment: str
    open_time: datetime
    expiration: Optional[datetime] = None


@dataclass
class MTSymbolInfo:
    name: str
    digits: int
    spread: int
    swap_long: float
    swap_short: float
    min_volume: float
    max_volume: float
    volume_step: float
    bid: float
    ask: float
    point: float
    tick_value: float
    tick_size: float
    contract_size: float
    trade_mode: int


@dataclass
class MTTick:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    time: datetime


class MTRuntimeError(Exception):
    pass


class MTRuntime(ABC):
    def __init__(self, config: MTConnectionConfig):
        self.config = config
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool: ...

    async def disconnect(self) -> None:
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def account_info(self) -> MTAccountInfo: ...

    @abstractmethod
    async def get_positions(self) -> List[MTPosition]: ...

    @abstractmethod
    async def get_orders(self) -> List[MTOrder]: ...

    @abstractmethod
    async def get_symbols(self) -> List[MTSymbolInfo]: ...

    @abstractmethod
    async def get_ticks(self, symbol: str, count: int = 10) -> List[MTTick]: ...

    @abstractmethod
    async def get_rates(self, symbol: str, timeframe: int, count: int = 100) -> List[Dict]: ...

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        order_type: int,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        comment: str = "",
    ) -> int: ...

    @abstractmethod
    async def cancel_order(self, ticket: int) -> bool: ...

    @abstractmethod
    async def modify_sl(self, ticket: int, sl: float) -> bool: ...

    @abstractmethod
    async def partial_close(self, ticket: int, volume: float) -> bool: ...


class MTRuntimeMock(MTRuntime):
    def __init__(self, config: MTConnectionConfig):
        super().__init__(config)
        self._symbols: Dict[str, MTSymbolInfo] = {}
        self._positions: List[MTPosition] = []
        self._orders: List[MTOrder] = []
        self._order_counter: int = 1000

    def _next_ticket(self) -> int:
        self._order_counter += 1
        return self._order_counter

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
        ticket = self._next_ticket()
        self._orders.append(MTOrder(
            ticket=ticket,
            symbol=symbol.upper(),
            type=order_type,
            volume=volume,
            price=price,
            stop_loss=sl,
            take_profit=tp,
            comment=comment,
            open_time=datetime.utcnow(),
        ))
        return ticket

    async def cancel_order(self, ticket: int) -> bool:
        before = len(self._orders)
        self._orders = [o for o in self._orders if o.ticket != ticket]
        return len(self._orders) < before

    async def modify_sl(self, ticket: int, sl: float) -> bool:
        for pos in self._positions:
            if pos.ticket == ticket:
                self._positions[self._positions.index(pos)] = MTPosition(
                    ticket=pos.ticket, symbol=pos.symbol, type=pos.type,
                    volume=pos.volume, open_price=pos.open_price,
                    current_price=pos.current_price, stop_loss=sl,
                    take_profit=pos.take_profit, profit=pos.profit,
                    swap=pos.swap, comment=pos.comment, open_time=pos.open_time,
                )
                return True
        return False

    async def partial_close(self, ticket: int, volume: float) -> bool:
        for pos in self._positions:
            if pos.ticket == ticket:
                if volume >= pos.volume:
                    return False
                self._positions[self._positions.index(pos)] = MTPosition(
                    ticket=pos.ticket, symbol=pos.symbol, type=pos.type,
                    volume=round(pos.volume - volume, 2),
                    open_price=pos.open_price, current_price=pos.current_price,
                    stop_loss=pos.stop_loss, take_profit=pos.take_profit,
                    profit=pos.profit, swap=pos.swap, comment=pos.comment,
                    open_time=pos.open_time,
                )
                return True
        return False

    async def connect(self) -> bool:
        self._connected = True
        self._symbols = {
            "XAUUSD": MTSymbolInfo(
                name="XAUUSD", digits=2, spread=25,
                swap_long=-3.5, swap_short=1.2,
                min_volume=0.01, max_volume=100.0, volume_step=0.01,
                bid=2350.00, ask=2350.25, point=0.01,
                tick_value=1.0, tick_size=0.01, contract_size=100.0,
                trade_mode=0,
            ),
            "NAS100": MTSymbolInfo(
                name="NAS100", digits=2, spread=15,
                swap_long=-2.0, swap_short=-1.5,
                min_volume=0.01, max_volume=100.0, volume_step=0.01,
                bid=19500.0, ask=19500.15, point=0.01,
                tick_value=0.5, tick_size=0.01, contract_size=10.0,
                trade_mode=0,
            ),
            "BTCUSD": MTSymbolInfo(
                name="BTCUSD", digits=2, spread=80,
                swap_long=-5.0, swap_short=-3.0,
                min_volume=0.01, max_volume=10.0, volume_step=0.01,
                bid=65000.0, ask=65000.80, point=0.01,
                tick_value=1.0, tick_size=0.01, contract_size=1.0,
                trade_mode=0,
            ),
        }
        return True

    async def account_info(self) -> MTAccountInfo:
        login_str = "".join(c for c in self.config.login if c.isdigit()) or "0"
        return MTAccountInfo(
            login=int(login_str),
            balance=10000.0,
            equity=9950.0,
            margin=500.0,
            margin_free=9450.0,
            margin_level=1990.0,
            leverage=100,
            currency="USD",
            server=self.config.server,
            name=f"Account {self.config.login}",
            company="Mock Broker Ltd",
            is_demo=True,
            trade_mode=0,
            connected=True,
        )

    async def get_positions(self) -> List[MTPosition]:
        return self._positions

    async def get_orders(self) -> List[MTOrder]:
        return self._orders

    async def get_symbols(self) -> List[MTSymbolInfo]:
        return list(self._symbols.values())

    async def get_ticks(self, symbol: str, count: int = 10) -> List[MTTick]:
        return [
            MTTick(
                symbol=symbol, bid=2350.00 + i * 0.1,
                ask=2350.25 + i * 0.1, last=2350.10 + i * 0.1,
                volume=10, time=datetime.utcnow(),
            )
            for i in range(count)
        ]

    async def get_rates(self, symbol: str, timeframe: int, count: int = 100) -> List[Dict]:
        return [
            {
                "time": datetime.utcnow(),
                "open": 2350.0, "high": 2355.0,
                "low": 2345.0, "close": 2352.0,
                "tick_volume": 1000, "spread": 25,
            }
            for _ in range(count)
        ]


def get_attr(obj, *names, default=None):
    for name in names:
        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def create_mt_runtime(config: MTConnectionConfig) -> MTRuntime:
    platform = config.platform.upper()
    if platform == "MT5":
        try:
            from core_engine.mt5_runtime import MT5Runtime
            return MT5Runtime(config)
        except ImportError:
            logger = logging.getLogger(__name__)
            logger.warning("MetaTrader5 not installed, falling back to mock")
            return MTRuntimeMock(config)
    # MT5-only product: MT4 runtimes are no longer created. Unknown platforms
    # fall back to the mock so callers keep a usable object, but the account
    # provisioning layer rejects non-MT5 platforms before this is reached.
    return MTRuntimeMock(config)
