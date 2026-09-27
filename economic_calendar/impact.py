"""Deterministic impact classification for US economic events.

Classification is configurable via the HIGH/MEDIUM keyword lists.
Only US/USD events are classified — non-US events should be filtered
before reaching this module.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


# ── Default keyword rules (US-only) ──────────────────────────────

# Exact and substring matches — checked in order; first match wins.
_DEFAULT_HIGH: List[str] = [
    # Employment
    "EMPLOYMENT SITUATION",
    "NON-FARM PAYROLLS",
    "NON FARM PAYROLLS",
    "NFP",
    "UNEMPLOYMENT RATE",
    "JOBS REPORT",
    "PAYROLLS",
    # Inflation
    "CONSUMER PRICE INDEX",
    "CPI",
    "CORE CPI",
    "PERSONAL CONSUMPTION EXPENDITURES",
    "PCE PRICE INDEX",
    "CORE PCE",
    "PCE",
    # Production / wholesale
    "PRODUCER PRICE INDEX",
    "PPI",
    "CORE PPI",
    # GDP
    "GROSS DOMESTIC PRODUCT",
    "GDP",
    "ADVANCE GDP",
    "SECOND GDP",
    "THIRD GDP",
    "REAL GDP",
    # Monetary policy
    "FOMC",
    "FEDERAL OPEN MARKET COMMITTEE",
    "FED RATE DECISION",
    "FEDERAL RESERVE RATE",
    "INTEREST RATE DECISION",
    "RATE DECISION",
    "FOMC STATEMENT",
    "FOMC MINUTES",
    "POWELL",
    "FED CHAIR",
    "FEDERAL RESERVE CHAIR",
]

_DEFAULT_MEDIUM: List[str] = [
    # Manufacturing / services
    "ISM MANUFACTURING",
    "ISM SERVICES",
    "PMI",
    "MARKIT MANUFACTURING",
    "MARKIT SERVICES",
    # Employment
    "INITIAL JOBLESS CLAIMS",
    "JOBLESS CLAIMS",
    "CONTINUING CLAIMS",
    "ADP EMPLOYMENT",
    "NONFARM PAYROLLS",
    # Housing
    "EXISTING HOME SALES",
    "NEW HOME SALES",
    "HOUSING STARTS",
    "BUILDING PERMITS",
    "CASE-SHILLER",
    "FHFA HOUSE PRICE",
    # Consumer
    "RETAIL SALES",
    "CORE RETAIL SALES",
    "CONSUMER CONFIDENCE",
    "UMICH CONSUMER SENTIMENT",
    "UNIVERSITY OF MICHIGAN",
    "CONSUMER SENTIMENT",
    # Income / spending
    "PERSONAL INCOME",
    "PERSONAL SPENDING",
    "DURABLE GOODS",
    "DURABLE GOODS ORDERS",
    "CORE DURABLE GOODS",
    # Industrial
    "INDUSTRIAL PRODUCTION",
    "CAPACITY UTILIZATION",
    # Trade
    "TRADE BALANCE",
    "IMPORT PRICE INDEX",
    "EXPORT PRICE INDEX",
    # Other medium
    "FED BEIGE BOOK",
    "BEIGE BOOK",
]

_DEFAULT_LOW: List[str] = [
    "FED SPEECH",
    "FED GOVERNOR SPEECH",
    "SPEECH",
    "TREASURY AUCTION",
    "AUCTION",
    "BUDGET STATEMENT",
    "FED BALANCE SHEET",
    "MONEY SUPPLY",
    "CONSUMER CREDIT",
    "JOLTs",
    "JOB OPENINGS",
    "WAGE GROWTH",
]


@dataclass
class ImpactClassification:
    """Result of impact classification."""
    event_name: str
    impact: str          # HIGH | MEDIUM | LOW
    category: str        # inflation | employment | gdp | monetary | housing | consumer | manufacturing | trade | other
    reason: str
    matched_keyword: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ImpactClassifier:
    """Deterministic, configurable US-only impact classifier.

    Usage::

        classifier = ImpactClassifier()
        result = classifier.classify("Consumer Price Index (CPI)")
        assert result.impact == "HIGH"
        assert result.category == "inflation"
    """

    # Category inference from keywords
    _CATEGORY_KEYWORDS: Dict[str, List[str]] = {
        "inflation": [
            "CPI", "CONSUMER PRICE INDEX", "INFLATION",
            "PCE", "CORE PCE", "PERSONAL CONSUMPTION EXPENDITURES",
            "PPI", "PRODUCER PRICE INDEX", "IMPORT PRICE", "EXPORT PRICE",
        ],
        "employment": [
            "EMPLOYMENT SITUATION", "NON-FARM PAYROLLS", "NON FARM PAYROLLS",
            "NFP", "UNEMPLOYMENT RATE", "JOBS REPORT", "PAYROLLS",
            "JOBLESS CLAIMS", "INITIAL JOBLESS", "CONTINUING CLAIMS",
            "ADP EMPLOYMENT", "JOLT", "JOB OPENINGS", "WAGE GROWTH",
        ],
        "gdp": [
            "GDP", "GROSS DOMESTIC PRODUCT", "REAL GDP",
        ],
        "monetary": [
            "FOMC", "FEDERAL OPEN MARKET", "FED RATE", "FEDERAL RESERVE RATE",
            "INTEREST RATE DECISION", "RATE DECISION", "FOMC STATEMENT",
            "FOMC MINUTES", "POWELL", "FED CHAIR", "FED GOVERNOR",
            "FED BEIGE BOOK", "BEIGE BOOK", "FED BALANCE SHEET", "MONEY SUPPLY",
        ],
        "housing": [
            "EXISTING HOME SALES", "NEW HOME SALES", "HOUSING STARTS",
            "BUILDING PERMITS", "CASE-SHILLER", "FHFA",
        ],
        "consumer": [
            "RETAIL SALES", "CORE RETAIL SALES", "CONSUMER CONFIDENCE",
            "UMICH CONSUMER SENTIMENT", "UNIVERSITY OF MICHIGAN",
            "CONSUMER SENTIMENT", "CONSUMER CREDIT",
        ],
        "manufacturing": [
            "ISM MANUFACTURING", "ISM SERVICES", "PMI", "MARKIT",
            "DURABLE GOODS", "INDUSTRIAL PRODUCTION", "CAPACITY UTILIZATION",
        ],
        "trade": [
            "TRADE BALANCE", "IMPORT PRICE INDEX", "EXPORT PRICE INDEX",
        ],
    }

    def __init__(
        self,
        high_keywords: Optional[List[str]] = None,
        medium_keywords: Optional[List[str]] = None,
        low_keywords: Optional[List[str]] = None,
    ):
        self.high_keywords = high_keywords if high_keywords is not None else list(_DEFAULT_HIGH)
        self.medium_keywords = medium_keywords if medium_keywords is not None else list(_DEFAULT_MEDIUM)
        self.low_keywords = low_keywords if low_keywords is not None else list(_DEFAULT_LOW)

    def classify(self, event_name: str) -> ImpactClassification:
        """Classify a US economic event by impact and category.

        Args:
            event_name: The event title (e.g. "Consumer Price Index (CPI)").

        Returns:
            ImpactClassification with impact, category, and reason.
        """
        name = str(event_name or "").upper().strip()

        # ── Impact classification (keyword match) ────────────────
        impact = "LOW"
        reason = "No matching keyword — defaulting to LOW"
        matched_kw: Optional[str] = None

        for kw in self.high_keywords:
            if kw.upper() in name:
                impact = "HIGH"
                reason = f"Matched HIGH keyword: {kw}"
                matched_kw = kw
                break

        if impact != "HIGH":
            for kw in self.medium_keywords:
                if kw.upper() in name:
                    impact = "MEDIUM"
                    reason = f"Matched MEDIUM keyword: {kw}"
                    matched_kw = kw
                    break

        if impact == "LOW":
            for kw in self.low_keywords:
                if kw.upper() in name:
                    impact = "LOW"
                    reason = f"Matched LOW keyword: {kw}"
                    matched_kw = kw
                    break

        # ── Category inference ────────────────────────────────────
        category = "other"
        for cat, keywords in self._CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in name:
                    category = cat
                    break
            if category != "other":
                break

        return ImpactClassification(
            event_name=event_name,
            impact=impact,
            category=category,
            reason=reason,
            matched_keyword=matched_kw,
        )

    def is_high_impact(self, event_name: str) -> bool:
        return self.classify(event_name).impact == "HIGH"

    def is_medium_or_high(self, event_name: str) -> bool:
        return self.classify(event_name).impact in ("MEDIUM", "HIGH")
