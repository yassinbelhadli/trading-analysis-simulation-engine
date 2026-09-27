from dataclasses import dataclass, asdict
import pandas as pd


@dataclass
class NewsConfirmationResult:
    allowed: bool
    score: int
    confirmations: int
    required_confirmations: int
    decayed_strength: float
    reason: str

    def to_dict(self):
        return asdict(self)


class PostNewsConfirmation:
    def __init__(
        self,
        required_confirmations: int = 2,
        wait_after_news_minutes: int = 10,
        news_decay_minutes: int = 120,
    ):
        self.required_confirmations = required_confirmations
        self.wait_after_news_minutes = wait_after_news_minutes
        self.news_decay_minutes = news_decay_minutes

    def evaluate(
        self,
        row: pd.Series,
        news_strength: float,
        news_bias: str,
        trade_direction: str,
        minutes_after_news: float,
    ) -> NewsConfirmationResult:

        if minutes_after_news < self.wait_after_news_minutes:
            return NewsConfirmationResult(
                allowed=False,
                score=0,
                confirmations=0,
                required_confirmations=self.required_confirmations,
                decayed_strength=0.0,
                reason="WAIT_AFTER_NEWS",
            )

        if news_bias == "SELL_ONLY" and trade_direction != "SELL":
            return NewsConfirmationResult(False, 0, 0, self.required_confirmations, 0.0, "NEWS_DIRECTION_CONFLICT")

        if news_bias == "BUY_ONLY" and trade_direction != "BUY":
            return NewsConfirmationResult(False, 0, 0, self.required_confirmations, 0.0, "NEWS_DIRECTION_CONFLICT")

        decayed_strength = self._apply_news_decay(news_strength, minutes_after_news)

        confirmations = 0
        score = 0

        if bool(row.get("MSS", False)) or bool(row.get("CHoCH", False)):
            confirmations += 1
            score += 25

        if bool(row.get("Sweep_Confirmed", False)):
            confirmations += 1
            score += 25

        if pd.notna(row.get("Active_OB_Type")) or pd.notna(row.get("Active_FVG_Type")):
            confirmations += 1
            score += 20

        if bool(row.get("Displacement", False)):
            score += 15

        if bool(row.get("Candle_Confirmation", False)):
            score += 15

        if decayed_strength >= 80:
            score += 10
        elif decayed_strength >= 50:
            score += 5

        allowed = confirmations >= self.required_confirmations

        return NewsConfirmationResult(
            allowed=allowed,
            score=score,
            confirmations=confirmations,
            required_confirmations=self.required_confirmations,
            decayed_strength=round(decayed_strength, 2),
            reason="CONFIRMED" if allowed else "NOT_ENOUGH_CONFIRMATIONS",
        )

    def _apply_news_decay(self, strength: float, minutes_after_news: float) -> float:
        if minutes_after_news <= self.wait_after_news_minutes:
            return strength

        if minutes_after_news >= self.news_decay_minutes:
            return 0.0

        decay_ratio = 1 - (minutes_after_news / self.news_decay_minutes)
        return max(0.0, strength * decay_ratio)