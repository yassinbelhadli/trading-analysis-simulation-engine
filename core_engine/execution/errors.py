"""Exception hierarchy + MT5 retcode → semantic error mapping.

Every broker-specific error code is mapped to a typed exception.
The rest of the codebase never sees raw retcodes.
"""

from __future__ import annotations
from typing import Dict, Optional


# ── Base ──────────────────────────────────────────────────────────

class ExecutionError(Exception):
    """Base for all execution errors."""


# ── Connection ────────────────────────────────────────────────────

class ConnectionError(ExecutionError):
    """Broker connection lost or unavailable."""


class BrokerNotConnectedError(ExecutionError):
    """Operation attempted while broker is disconnected."""


# ── Order lifecycle ───────────────────────────────────────────────

class OrderRejectedError(ExecutionError):
    """Order was rejected by broker."""


class OrderTimeoutError(ExecutionError):
    """Order did not fill within expected time."""


class SlippageExceededError(ExecutionError):
    """Actual fill price exceeded configured slippage tolerance."""


class InvalidOrderError(ExecutionError):
    """Order parameters are invalid (e.g. price out of range)."""


class InvalidVolumeError(InvalidOrderError):
    """Lot/unit size is invalid for this symbol."""


class InvalidStopsError(InvalidOrderError):
    """Stop-loss or take-profit levels are invalid."""


class RetryExhaustedError(ExecutionError):
    """Operation failed after all retry attempts."""


# ── Market state ──────────────────────────────────────────────────

class MarketClosedError(ExecutionError):
    """Symbol market is closed."""


class NoMoneyError(ExecutionError):
    """Insufficient margin to open position."""


class TradeDisabledError(ExecutionError):
    """Trading disabled for this symbol or account."""


class RequoteError(ExecutionError):
    """Price changed before fill (requote)."""


# ── MT5 retcode → exception mapping ───────────────────────────────

MT5_RETCODE_MAP: Dict[int, str] = {
    10004: "REQUOTE",
    10006: "REJECT",
    10007: "CANCEL",
    10008: "PLACED",
    10009: "DONE",
    10010: "DONE_PARTIAL",
    10011: "ERROR",
    10012: "TIMEOUT",
    10013: "INVALID",
    10014: "INVALID_VOLUME",
    10015: "INVALID_PRICE",
    10016: "INVALID_STOPS",
    10017: "TRADE_DISABLED",
    10018: "MARKET_CLOSED",
    10019: "NO_MONEY",
    10020: "PRICE_CHANGED",
    10021: "PRICE_OFF",
    10022: "INVALID_EXPIRATION",
    10023: "ORDER_CHANGED",
    10024: "TOO_MANY_REQUESTS",
    10025: "NO_CHANGES",
    10026: "SERVER_DISABLES_AT",
    10027: "UNKNOWN_SYMBOL",
    10028: "NO_OPEN_SPACE",
}


def map_retcode(retcode: int, comment: str = "") -> ExecutionError:
    """Map MT5 retcode to a typed exception.

    Args:
        retcode: MT5 trade retcode integer
        comment: optional comment from MT5 result

    Returns:
        Appropriate ExecutionError subclass.
    """
    label = MT5_RETCODE_MAP.get(retcode, f"UNKNOWN_{retcode}")
    msg = f"[{label}] {comment}" if comment else f"[{label}]"

    if retcode == 10004:
        return RequoteError(msg)
    elif retcode == 10014:
        return InvalidVolumeError(msg)
    elif retcode == 10015:
        return InvalidOrderError(msg)
    elif retcode == 10016:
        return InvalidStopsError(msg)
    elif retcode == 10017:
        return TradeDisabledError(msg)
    elif retcode == 10018:
        return MarketClosedError(msg)
    elif retcode == 10019:
        return NoMoneyError(msg)
    elif retcode in (10006, 10007, 10011):
        return OrderRejectedError(msg)
    elif retcode in (10012, 10020, 10021):
        return OrderTimeoutError(msg)
    elif retcode in (10013, 10022, 10023, 10024, 10025, 10026, 10027, 10028):
        return InvalidOrderError(msg)
    else:
        return ExecutionError(msg)
