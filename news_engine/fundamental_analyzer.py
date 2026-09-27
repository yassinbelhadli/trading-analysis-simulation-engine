# fundamental_analyzer.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import pandas as pd


@dataclass
class FundamentalResult:
    event: str
    currency: str
    impact: str
    actual: Optional[float]
    forecast: Optional[float]
    previous: Optional[float]

    currency_bias: str
    xauusd_bias: str
    nas100_bias: str
    btcusd_bias: str

    strength: float
    confidence: float
    surprise: Optional[float]
    surprise_ratio: Optional[float]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FundamentalAnalyzer:
    def __init__(
        self,
        min_surprise_ratio: float = 0.03,
        strong_surprise_ratio: float = 0.20,
    ):
        self.min_surprise_ratio = min_surprise_ratio
        self.strong_surprise_ratio = strong_surprise_ratio

    def analyze_event(
        self,
        event: str,
        currency: str,
        impact: str,
        actual=None,
        forecast=None,
        previous=None,
    ) -> FundamentalResult:

        event_name = str(event or "").upper().strip()
        currency = str(currency or "").upper().strip()
        impact = str(impact or "").upper().strip()

        actual_f = self._safe_float(actual)
        forecast_f = self._safe_float(forecast)
        previous_f = self._safe_float(previous)

        if actual_f is None or forecast_f is None:
            return self._neutral(
                event_name,
                currency,
                impact,
                actual_f,
                forecast_f,
                previous_f,
                "Missing actual or forecast",
            )

        surprise = actual_f - forecast_f
        base = abs(forecast_f) if abs(forecast_f) > 0 else 1.0
        surprise_ratio = abs(surprise) / base

        if surprise_ratio < self.min_surprise_ratio:
            return self._neutral(
                event_name,
                currency,
                impact,
                actual_f,
                forecast_f,
                previous_f,
                f"Surprise too small: {round(surprise_ratio, 4)}",
            )

        currency_bias = self._currency_bias(
            event_name=event_name,
            actual=actual_f,
            forecast=forecast_f,
        )

        if currency_bias == "NEUTRAL":
            return self._neutral(
                event_name,
                currency,
                impact,
                actual_f,
                forecast_f,
                previous_f,
                "No directional rule for this event",
            )

        strength = self._calculate_strength(
            surprise_ratio=surprise_ratio,
            impact=impact,
            event_name=event_name,
        )

        confidence = self._calculate_confidence(
            strength=strength,
            impact=impact,
            event_name=event_name,
        )

        xauusd_bias = self._asset_bias("XAUUSD", currency, currency_bias, event_name)
        nas100_bias = self._asset_bias("NAS100", currency, currency_bias, event_name)
        btcusd_bias = self._asset_bias("BTCUSD", currency, currency_bias, event_name)

        return FundamentalResult(
            event=event_name,
            currency=currency,
            impact=impact,
            actual=actual_f,
            forecast=forecast_f,
            previous=previous_f,
            currency_bias=currency_bias,
            xauusd_bias=xauusd_bias,
            nas100_bias=nas100_bias,
            btcusd_bias=btcusd_bias,
            strength=strength,
            confidence=confidence,
            surprise=round(surprise, 5),
            surprise_ratio=round(surprise_ratio, 5),
            reason=(
                f"{event_name}: actual={actual_f}, forecast={forecast_f}, "
                f"currency_bias={currency_bias}, strength={strength}"
            ),
        )

    def analyze_row(self, row: pd.Series) -> FundamentalResult:
        return self.analyze_event(
            event=row.get("event", row.get("event_name", "")),
            currency=row.get("currency", ""),
            impact=row.get("impact", ""),
            actual=row.get("actual", None),
            forecast=row.get("forecast", None),
            previous=row.get("previous", None),
        )

    def _currency_bias(self, event_name: str, actual: float, forecast: float) -> str:
        higher_bullish = [
            "CPI",
            "CORE CPI",
            "PCE",
            "CORE PCE",
            "INFLATION",
            "NFP",
            "NON FARM",
            "PAYROLLS",
            "EMPLOYMENT CHANGE",
            "GDP",
            "RETAIL SALES",
            "PMI",
            "ISM",
            "INTEREST RATE",
            "RATE DECISION",
        ]

        lower_bullish = [
            "UNEMPLOYMENT",
            "UNEMPLOYMENT RATE",
            "JOBLESS CLAIMS",
            "UNEMPLOYMENT CLAIMS",
            "CLAIMS",
        ]

        if any(k in event_name for k in higher_bullish):
            if actual > forecast:
                return "BULLISH"
            if actual < forecast:
                return "BEARISH"

        if any(k in event_name for k in lower_bullish):
            if actual < forecast:
                return "BULLISH"
            if actual > forecast:
                return "BEARISH"

        return "NEUTRAL"

    def _asset_bias(
        self,
        symbol: str,
        currency: str,
        currency_bias: str,
        event_name: str,
    ) -> str:

        if currency != "USD":
            return "NEUTRAL"

        symbol = symbol.upper()

        if currency_bias == "BULLISH":
            if symbol == "XAUUSD":
                return "SELL_ONLY"
            if symbol == "NAS100":
                return "SELL_ONLY"
            if symbol == "BTCUSD":
                return "SELL_ONLY"

        if currency_bias == "BEARISH":
            if symbol == "XAUUSD":
                return "BUY_ONLY"
            if symbol == "NAS100":
                return "BUY_ONLY"
            if symbol == "BTCUSD":
                return "BUY_ONLY"

        return "NEUTRAL"

    def _calculate_strength(
        self,
        surprise_ratio: float,
        impact: str,
        event_name: str,
    ) -> float:

        raw = min((surprise_ratio / self.strong_surprise_ratio) * 100, 100)

        if impact == "HIGH":
            raw *= 1.15
        elif impact == "MEDIUM":
            raw *= 0.85
        else:
            raw *= 0.60

        major_events = [
            "CPI",
            "CORE CPI",
            "PCE",
            "CORE PCE",
            "NFP",
            "PAYROLLS",
            "FOMC",
            "RATE DECISION",
            "INTEREST RATE",
            "GDP",
        ]

        if any(k in event_name for k in major_events):
            raw *= 1.10

        return round(min(raw, 100), 2)

    def _calculate_confidence(
        self,
        strength: float,
        impact: str,
        event_name: str,
    ) -> float:

        confidence = strength

        if impact == "HIGH":
            confidence += 10
        elif impact == "MEDIUM":
            confidence += 3

        if any(k in event_name for k in ["CPI", "PCE", "NFP", "FOMC", "GDP"]):
            confidence += 5

        return round(min(confidence, 100), 2)

    def _neutral(
        self,
        event,
        currency,
        impact,
        actual,
        forecast,
        previous,
        reason,
    ) -> FundamentalResult:

        return FundamentalResult(
            event=event,
            currency=currency,
            impact=impact,
            actual=actual,
            forecast=forecast,
            previous=previous,
            currency_bias="NEUTRAL",
            xauusd_bias="NEUTRAL",
            nas100_bias="NEUTRAL",
            btcusd_bias="NEUTRAL",
            strength=0.0,
            confidence=0.0,
            surprise=None,
            surprise_ratio=None,
            reason=reason,
        )

    def _safe_float(self, value):
        try:
            if value is None:
                return None
            if pd.isna(value):
                return None

            v = str(value).replace("%", "").replace(",", "").strip()

            if v == "":
                return None

            return float(v)
        except Exception:
            return None