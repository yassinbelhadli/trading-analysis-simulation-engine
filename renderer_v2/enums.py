from enum import Enum, auto


class LayerType(Enum):
    CANDLES = auto()
    STRUCTURE = auto()
    LIQUIDITY = auto()
    ORDER_BLOCK = auto()
    FVG = auto()
    SWINGS = auto()
    TRADES = auto()
    LABELS = auto()
    OVERLAY = auto()


class ElementType(Enum):
    # Chart
    CANDLE = auto()
    # Structure
    STRUCTURE = auto()    # BOS / CHOCH / MSS
    # Liquidity
    LIQUIDITY = auto()    # Sweep / PDH / PDL
    # Zones
    ORDER_BLOCK = auto()  # Bullish / Bearish
    FVG = auto()          # Bullish / Bearish
    # Swings
    SWING = auto()        # HH / HL / LH / LL
    # Trade
    TRADE = auto()        # Entry / SL / TP / Exit / Partial / BE
    # Pure annotation
    LABEL = auto()


class StructureKind(Enum):
    BOS = auto()
    CHOCH = auto()
    MSS = auto()


class LiquidityKind(Enum):
    SWEEP = auto()
    PDH = auto()
    PDL = auto()


class SwingKind(Enum):
    HH = auto()  # Higher High
    HL = auto()  # Higher Low
    LH = auto()  # Lower High
    LL = auto()  # Lower Low


class TradeKind(Enum):
    ENTRY = auto()
    STOP_LOSS = auto()
    TAKE_PROFIT = auto()
    EXIT = auto()
    PARTIAL = auto()
    BREAK_EVEN = auto()


class Direction(Enum):
    BULLISH = auto()
    BEARISH = auto()
    NEUTRAL = auto()


class CollisionPolicy(Enum):
    HIDE = auto()
    SHIFT = auto()
    STACK = auto()
    MERGE = auto()
    SHORTEN = auto()
    FADE = auto()
    NONE = auto()
