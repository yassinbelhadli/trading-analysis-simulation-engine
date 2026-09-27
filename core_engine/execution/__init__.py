"""Execution layer — broker abstraction, order management, trade lifecycle, guards."""

from .errors import (
    ExecutionError,
    ConnectionError,
    OrderRejectedError,
    OrderTimeoutError,
    SlippageExceededError,
    InvalidOrderError,
    InvalidVolumeError,
    InvalidStopsError,
    RetryExhaustedError,
    BrokerNotConnectedError,
    MarketClosedError,
    NoMoneyError,
    TradeDisabledError,
    RequoteError,
    map_retcode,
)

from .retry import retry
from .reconnect import ReconnectManager

from .broker import (
    BrokerAdapter,
    PaperBroker,
    OrderResult,
    PositionInfo,
    BrokerEvent,
    OrderSide,
    OrderType,
)

from .order_manager import OrderManager, ManagedTrade

from .mt5_adapter import MT5Adapter

from .execution_engine import ExecutionEngine, ExecutionResult
from .execution_guard import ExecutionGuard, GuardResult
from .trade_planner import TradePlanner, TradePlan, PlanValidation
from .trade_manager import TradeManager, TradeManagementAction
from .trade_lifecycle import TradeLifecycleManager
from .entry_manager import EntryManager, EntryDecision
from .paper_trading import PaperTradingService

from .break_even import BreakEvenManager, BreakEvenResult
from .partial_close import PartialCloseManager, PartialCloseResult
from .trailing_stop import TrailingStopManager, TrailingStopResult
from .recovery import RecoveryManager, RecoveredTrade

__all__ = [
    "ExecutionError",
    "ConnectionError",
    "OrderRejectedError",
    "OrderTimeoutError",
    "SlippageExceededError",
    "InvalidOrderError",
    "RetryExhaustedError",
    "BrokerNotConnectedError",
    "retry",
    "ReconnectManager",
    "BrokerAdapter",
    "PaperBroker",
    "OrderResult",
    "PositionInfo",
    "BrokerEvent",
    "OrderSide",
    "OrderType",
    "OrderManager",
    "ManagedTrade",
    "MT5Adapter",
    "ExecutionEngine",
    "ExecutionResult",
    "ExecutionGuard",
    "GuardResult",
    "TradePlanner",
    "TradePlan",
    "PlanValidation",
    "TradeManager",
    "TradeManagementAction",
    "TradeLifecycleManager",
    "EntryManager",
    "EntryDecision",
    "PaperTradingService",
    "BreakEvenManager",
    "BreakEvenResult",
    "PartialCloseManager",
    "PartialCloseResult",
    "TrailingStopManager",
    "TrailingStopResult",
    "InvalidVolumeError",
    "InvalidStopsError",
    "MarketClosedError",
    "NoMoneyError",
    "TradeDisabledError",
    "RequoteError",
    "map_retcode",
    "RecoveryManager",
    "RecoveredTrade",
]
