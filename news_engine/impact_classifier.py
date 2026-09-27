# impact_classifier.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass
class ImpactClassification:
    event_name: str
    currency: Optional[str]
    impact: str
    category: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ImpactClassifier:
    HIGH_KEYWORDS = [
        "NFP",
        "NON FARM",
        "NON-FARM",
        "CPI",
        "CORE CPI",
        "INFLATION",
        "FOMC",
        "FED",
        "FEDERAL RESERVE",
        "INTEREST RATE",
        "RATE DECISION",
        "POWELL",
        "ECB",
        "BOE",
        "BOJ",
        "SNB",
        "RBA",
        "RBNZ",
        "GDP",
        "UNEMPLOYMENT RATE",
        "JOBS REPORT",
        "PAYROLLS",
    ]

    MEDIUM_KEYWORDS = [
        "PMI",
        "ISM",
        "PPI",
        "RETAIL SALES",
        "JOBLESS CLAIMS",
        "CONSUMER CONFIDENCE",
        "DURABLE GOODS",
        "INDUSTRIAL PRODUCTION",
        "HOUSING",
        "EXISTING HOME SALES",
        "NEW HOME SALES",
    ]

    LOW_KEYWORDS = [
        "SPEECH",
        "AUCTION",
        "INVENTORIES",
        "BALANCE",
        "IMPORT",
        "EXPORT",
    ]

    HIGH_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]

    def classify(
        self,
        event_name: str,
        currency: Optional[str] = None,
        provided_impact: Optional[str] = None,
    ) -> ImpactClassification:
        name = str(event_name or "").upper().strip()
        cur = str(currency or "").upper().strip() if currency else None
        raw_impact = str(provided_impact or "").upper().strip()

        if raw_impact in ["HIGH", "RED", "3", "3_STAR", "HIGH IMPACT"]:
            return ImpactClassification(event_name, cur, "HIGH", "PROVIDED", "Provided impact is high")

        if raw_impact in ["MEDIUM", "ORANGE", "2", "2_STAR", "MEDIUM IMPACT"]:
            return ImpactClassification(event_name, cur, "MEDIUM", "PROVIDED", "Provided impact is medium")

        if raw_impact in ["LOW", "YELLOW", "1", "1_STAR", "LOW IMPACT"]:
            return ImpactClassification(event_name, cur, "LOW", "PROVIDED", "Provided impact is low")

        for kw in self.HIGH_KEYWORDS:
            if kw in name:
                return ImpactClassification(event_name, cur, "HIGH", "KEYWORD", f"Matched high keyword: {kw}")

        for kw in self.MEDIUM_KEYWORDS:
            if kw in name:
                return ImpactClassification(event_name, cur, "MEDIUM", "KEYWORD", f"Matched medium keyword: {kw}")

        for kw in self.LOW_KEYWORDS:
            if kw in name:
                return ImpactClassification(event_name, cur, "LOW", "KEYWORD", f"Matched low keyword: {kw}")

        if cur in self.HIGH_CURRENCIES:
            return ImpactClassification(event_name, cur, "MEDIUM", "CURRENCY_DEFAULT", "Major currency default")

        return ImpactClassification(event_name, cur, "LOW", "DEFAULT", "No strong impact keyword found")

    def is_high_impact(self, event_name: str, currency: Optional[str] = None, provided_impact: Optional[str] = None) -> bool:
        return self.classify(event_name, currency, provided_impact).impact == "HIGH"

    def is_medium_or_high(self, event_name: str, currency: Optional[str] = None, provided_impact: Optional[str] = None) -> bool:
        return self.classify(event_name, currency, provided_impact).impact in ["MEDIUM", "HIGH"]