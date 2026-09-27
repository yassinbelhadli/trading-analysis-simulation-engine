from dataclasses import dataclass, asdict
from typing import List
from collections import Counter

from news_engine.fundamental_analyzer import FundamentalResult


@dataclass
class AggregatedFundamentalResult:
    currency: str
    bias: str
    strength: float
    confidence: float
    events: int
    high_events: int
    medium_events: int
    low_events: int
    bullish_events: int
    bearish_events: int
    neutral_events: int
    bullish_weight: float
    bearish_weight: float
    neutral_weight: float
    reason: str

    def to_dict(self):
        return asdict(self)


class EventAggregator:
    def aggregate(
        self,
        results: List[FundamentalResult],
    ) -> AggregatedFundamentalResult:

        if not results:
            return AggregatedFundamentalResult(
                currency="UNKNOWN",
                bias="NEUTRAL",
                strength=0.0,
                confidence=0.0,
                events=0,
                high_events=0,
                medium_events=0,
                low_events=0,
                bullish_events=0,
                bearish_events=0,
                neutral_events=0,
                bullish_weight=0.0,
                bearish_weight=0.0,
                neutral_weight=0.0,
                reason="NO_EVENTS",
            )

        currency = results[0].currency

        impact_counter = Counter()
        bias_counter = Counter()

        bullish_weight = 0.0
        bearish_weight = 0.0
        neutral_weight = 0.0

        weighted_strength_total = 0.0
        weighted_confidence_total = 0.0
        total_weight = 0.0

        for r in results:
            impact_counter[r.impact] += 1
            bias_counter[r.currency_bias] += 1

            weight = self._event_weight(r)

            weighted_strength_total += r.strength * weight
            weighted_confidence_total += r.confidence * weight
            total_weight += weight

            if r.currency_bias == "BULLISH":
                bullish_weight += weight
            elif r.currency_bias == "BEARISH":
                bearish_weight += weight
            else:
                neutral_weight += weight

        bullish = bias_counter["BULLISH"]
        bearish = bias_counter["BEARISH"]
        neutral = bias_counter["NEUTRAL"]

        if bullish_weight > bearish_weight and bullish_weight > neutral_weight:
            bias = "BULLISH"
        elif bearish_weight > bullish_weight and bearish_weight > neutral_weight:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        if total_weight <= 0:
            strength = 0.0
            confidence = 0.0
        else:
            strength = weighted_strength_total / total_weight
            confidence = weighted_confidence_total / total_weight

        return AggregatedFundamentalResult(
            currency=currency,
            bias=bias,
            strength=round(strength, 2),
            confidence=round(confidence, 2),
            events=len(results),
            high_events=impact_counter["HIGH"],
            medium_events=impact_counter["MEDIUM"],
            low_events=impact_counter["LOW"],
            bullish_events=bullish,
            bearish_events=bearish,
            neutral_events=neutral,
            bullish_weight=round(bullish_weight, 2),
            bearish_weight=round(bearish_weight, 2),
            neutral_weight=round(neutral_weight, 2),
            reason=(
                f"weighted: bullish={bullish_weight:.2f}, "
                f"bearish={bearish_weight:.2f}, neutral={neutral_weight:.2f}"
            ),
        )

    def _event_weight(self, result: FundamentalResult) -> float:
        event = str(result.event or "").upper()
        impact = str(result.impact or "").upper()

        weight = 1.0

        if impact == "HIGH":
            weight += 2.0
        elif impact == "MEDIUM":
            weight += 1.0
        else:
            weight += 0.25

        major_events = [
            "FOMC",
            "RATE DECISION",
            "INTEREST RATE",
            "NFP",
            "NON FARM",
            "PAYROLLS",
            "CPI",
            "CORE CPI",
            "PCE",
            "CORE PCE",
            "GDP",
        ]

        medium_events = [
            "PMI",
            "ISM",
            "RETAIL SALES",
            "UNEMPLOYMENT CLAIMS",
            "JOBLESS CLAIMS",
            "CONSUMER SENTIMENT",
        ]

        speeches = [
            "SPEAKS",
            "SPEECH",
            "TESTIFIES",
        ]

        if any(k in event for k in major_events):
            weight += 2.0

        if any(k in event for k in medium_events):
            weight += 1.0

        if any(k in event for k in speeches):
            weight -= 0.5

        if result.strength >= 80:
            weight += 1.0
        elif result.strength >= 50:
            weight += 0.5

        return max(weight, 0.5)