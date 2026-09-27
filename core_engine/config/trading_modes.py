from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class TradingModeConfig:
    name: str
    description: str

    min_setup_score: float
    max_setup_score: float

    min_confidence_score: float

    min_risk_percent: float
    max_risk_percent: float

    max_trades_per_day: int
    max_trades_per_symbol_per_day: int

    required_news_confirmations: int
    wait_after_news_minutes: int

    min_rr: float
    allow_medium_news: bool
    allow_high_news_trading: bool

    allowed_sessions: List[str]
    allowed_symbols: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        return asdict(self)


TRADING_MODES = {
    "ULTRA_CONSERVATIVE": TradingModeConfig(
        name="ULTRA_CONSERVATIVE",
        description="Maximum capital protection. Best for funded accounts.",
        min_setup_score=85,
        max_setup_score=100,
        min_confidence_score=90,
        min_risk_percent=0.10,
        max_risk_percent=0.50,
        max_trades_per_day=2,
        max_trades_per_symbol_per_day=1,
        required_news_confirmations=3,
        wait_after_news_minutes=15,
        min_rr=2.0,
        allow_medium_news=False,
        allow_high_news_trading=False,
        allowed_sessions=["LONDON", "NEW_YORK"],
        allowed_symbols=["XAUUSD", "NAS100", "BTCUSD"],
    ),

    "CONSERVATIVE": TradingModeConfig(
        name="CONSERVATIVE",
        description="Safe trading with strict confirmations.",
        min_setup_score=75,
        max_setup_score=100,
        min_confidence_score=80,
        min_risk_percent=0.25,
        max_risk_percent=0.75,
        max_trades_per_day=3,
        max_trades_per_symbol_per_day=1,
        required_news_confirmations=3,
        wait_after_news_minutes=10,
        min_rr=1.8,
        allow_medium_news=True,
        allow_high_news_trading=False,
        allowed_sessions=["LONDON", "NEW_YORK"],
        allowed_symbols=["XAUUSD", "NAS100", "BTCUSD"],
    ),

    "BALANCED": TradingModeConfig(
        name="BALANCED",
        description="Balanced setup frequency and protection.",
        min_setup_score=65,
        max_setup_score=95,
        min_confidence_score=70,
        min_risk_percent=0.50,
        max_risk_percent=1.25,
        max_trades_per_day=5,
        max_trades_per_symbol_per_day=2,
        required_news_confirmations=2,
        wait_after_news_minutes=8,
        min_rr=1.5,
        allow_medium_news=True,
        allow_high_news_trading=True,
        allowed_sessions=["LONDON", "NEW_YORK"],
        allowed_symbols=["XAUUSD", "NAS100", "BTCUSD"],
    ),

    "AGGRESSIVE": TradingModeConfig(
        name="AGGRESSIVE",
        description="Higher activity. Risk increases with stronger setup score.",
        min_setup_score=50,
        max_setup_score=90,
        min_confidence_score=60,
        min_risk_percent=0.50,
        max_risk_percent=2.00,
        max_trades_per_day=10,
        max_trades_per_symbol_per_day=3,
        required_news_confirmations=2,
        wait_after_news_minutes=5,
        min_rr=1.3,
        allow_medium_news=True,
        allow_high_news_trading=True,
        allowed_sessions=["LONDON", "NEW_YORK"],
        allowed_symbols=["XAUUSD", "NAS100", "BTCUSD"],
    ),
}


def get_trading_mode(mode_name: str) -> TradingModeConfig:
    mode_name = str(mode_name or "CONSERVATIVE").upper().strip()

    if mode_name not in TRADING_MODES:
        return TRADING_MODES["CONSERVATIVE"]

    return TRADING_MODES[mode_name]


def calculate_mode_risk(mode_name: str, setup_score: float) -> float:
    mode = get_trading_mode(mode_name)

    score = max(mode.min_setup_score, min(float(setup_score), mode.max_setup_score))

    score_range = mode.max_setup_score - mode.min_setup_score
    risk_range = mode.max_risk_percent - mode.min_risk_percent

    if score_range <= 0:
        return round(mode.min_risk_percent, 2)

    ratio = (score - mode.min_setup_score) / score_range
    risk = mode.min_risk_percent + (ratio * risk_range)

    return round(risk, 2)
