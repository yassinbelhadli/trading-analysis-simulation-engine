"""Deterministic market-relevance mapping for US economic events.

Determines which events are relevant to our trading symbols:
  - XAUUSD  (Gold)
  - BTCUSD  (Bitcoin)
  - NASDAQ  (Nasdaq 100 / US100 / NAS100 / USTEC)

This mapping is used for:
  - Telegram notification filtering (which events to notify about)
  - Trading Risk Engine (which events trigger protection windows)

This does NOT generate trades.  It only determines relevance.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set


# ── Default relevance rules ───────────────────────────────────────

# Events matching these keywords are relevant to ALL three symbols.
_UNIVERSAL_KEYWORDS: List[str] = [
    "CPI",
    "CONSUMER PRICE INDEX",
    "CORE CPI",
    "NFP",
    "NON-FARM PAYROLLS",
    "NON FARM PAYROLLS",
    "NON-FARM EMPLOYMENT",
    "EMPLOYMENT SITUATION",
    "UNEMPLOYMENT RATE",
    "UNEMPLOYMENT CLAIMS",
    "ADP EMPLOYMENT",
    "FOMC",
    "FED RATE DECISION",
    "FEDERAL RESERVE",
    "GDP",
    "GROSS DOMESTIC PRODUCT",
    "PCE",
    "CORE PCE",
    "PERSONAL CONSUMPTION EXPENDITURES",
    "PPI",
    "PRODUCER PRICE INDEX",
    "CORE PPI",
    "POWELL",
    "FED CHAIR",
    "INTEREST RATE DECISION",
    "FOMC STATEMENT",
    "FOMC MINUTES",
]

# Events relevant to XAUUSD specifically (beyond universal)
_XAUUSD_KEYWORDS: List[str] = [
    "REAL YIELD",
    "TIPS",
    "INFLATION EXPECTATIONS",
    "DOLLAR INDEX",
    "US DXY",
]

# Events relevant to NASDAQ specifically (beyond universal)
_NASDAQ_KEYWORDS: List[str] = [
    "ISM MANUFACTURING",
    "ISM SERVICES",
    "PMI",
    "RETAIL SALES",
    "DURABLE GOODS",
    "INDUSTRIAL PRODUCTION",
    "CONSUMER CONFIDENCE",
    "CONSUMER SENTIMENT",
    "HOUSING STARTS",
    "BUILDING PERMITS",
]

# Events relevant to BTCUSD specifically (beyond universal)
_BTCUSD_KEYWORDS: List[str] = [
    "RISK APPETITE",
    "DOLLAR STRENGTH",
]


class MarketRelevanceMapper:
    """Maps economic events to relevant trading symbols.

    Usage::

        mapper = MarketRelevanceMapper()
        symbols = mapper.get_relevant_symbols("Consumer Price Index (CPI)")
        assert "XAUUSD" in symbols
        assert "BTCUSD" in symbols
        assert "NASDAQ" in symbols
    """

    ALL_SYMBOLS = ["XAUUSD", "BTCUSD", "NASDAQ"]

    def __init__(
        self,
        universal_keywords: Optional[List[str]] = None,
        xauusd_keywords: Optional[List[str]] = None,
        nasdaq_keywords: Optional[List[str]] = None,
        btcusd_keywords: Optional[List[str]] = None,
        custom_rules: Optional[Dict[str, List[str]]] = None,
    ):
        self.universal_keywords = universal_keywords if universal_keywords is not None else list(_UNIVERSAL_KEYWORDS)
        self.xauusd_keywords = xauusd_keywords if xauusd_keywords is not None else list(_XAUUSD_KEYWORDS)
        self.nasdaq_keywords = nasdaq_keywords if nasdaq_keywords is not None else list(_NASDAQ_KEYWORDS)
        self.btcusd_keywords = btcusd_keywords if btcusd_keywords is not None else list(_BTCUSD_KEYWORDS)
        self.custom_rules = custom_rules or {}

    def get_relevant_symbols(self, event_name: str) -> List[str]:
        """Return list of symbols relevant to this event.

        Args:
            event_name: The event title.

        Returns:
            Sorted list of relevant symbol strings. Empty list if not relevant.
        """
        name = str(event_name or "").upper().strip()
        symbols: Set[str] = set()

        # Universal — relevant to all
        for kw in self.universal_keywords:
            if kw.upper() in name:
                symbols.update(self.ALL_SYMBOLS)
                break

        # XAUUSD-specific
        if "XAUUSD" not in symbols:
            for kw in self.xauusd_keywords:
                if kw.upper() in name:
                    symbols.add("XAUUSD")
                    break

        # NASDAQ-specific
        if "NASDAQ" not in symbols:
            for kw in self.nasdaq_keywords:
                if kw.upper() in name:
                    symbols.add("NASDAQ")
                    break

        # BTCUSD-specific
        if "BTCUSD" not in symbols:
            for kw in self.btcusd_keywords:
                if kw.upper() in name:
                    symbols.add("BTCUSD")
                    break

        # Custom rules (pattern → symbols)
        for pattern, syms in self.custom_rules.items():
            if pattern.upper() in name:
                symbols.update(syms)

        return sorted(symbols)

    def is_relevant_to_any(self, event_name: str, symbols: Optional[List[str]] = None) -> bool:
        """Check if event is relevant to any of the given symbols.

        Args:
            event_name: The event title.
            symbols: Symbols to check. Defaults to ALL_SYMBOLS.
        """
        if symbols is None:
            symbols = self.ALL_SYMBOLS
        relevant = set(self.get_relevant_symbols(event_name))
        return bool(relevant.intersection(symbols))
