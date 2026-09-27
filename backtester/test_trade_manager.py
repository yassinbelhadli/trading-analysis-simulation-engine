import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.detection.market_structure import MarketStructureDetector
from core_engine.detection.liquidity import LiquidityEngine
from core_engine.detection.fair_value_gap import FVGDetector
from core_engine.detection.order_blocks import OrderBlockEngine
from core_engine.detection.volume_imbalance import VolumeImbalanceDetector
from core_engine.detection.liquidity_void import LiquidityVoidDetector
from core_engine.detection.premium_discount import PremiumDiscountDetector
from core_engine.detection.support_resistance import SupportResistanceDetector
from core_engine.detection.candle_patterns import CandlePatternDetector

from core_engine.scoring.score_engine import ScoreEngine
from core_engine.scoring.setup_ranker import SetupRanker
from core_engine.scoring.confidence_score import ConfidenceScoreEngine

from core_engine.sessions.killzones import KillzoneEngine
from core_engine.sessions.london_session import LondonSessionEngine
from core_engine.sessions.newyork_session import NewYorkSessionEngine

from core_engine.risk.weekend_guard import WeekendGuard
from core_engine.risk.account_profile import AccountProfileBuilder
from core_engine.risk.symbol_validator import SymbolValidator

from core_engine.execution.entry_manager import EntryManager
from core_engine.execution.trade_manager import TradeManager


DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_trade_manager_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)
df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

# 1. Full analysis pipeline
df = MarketStructureDetector().process_structure(df)
df = LiquidityEngine().process_liquidity(df)
df = FVGDetector().process_fvg(df)
df = OrderBlockEngine().process_order_blocks(df)
df = VolumeImbalanceDetector().process_volume_imbalance(df)
df = LiquidityVoidDetector().process_liquidity_void(df)
df = PremiumDiscountDetector().process_premium_discount(df)
df = SupportResistanceDetector().process_support_resistance(df)
df = CandlePatternDetector().process_candle_patterns(df)

df = ScoreEngine().process_score(df)

df = SetupRanker(
    min_score=70,
    premium_score=85,
    max_daily_setups=6,
    min_daily_setups_target=3,
    cooldown_candles=8,
    max_same_direction_per_day=4
).process_rankings(df)

df = ConfidenceScoreEngine(
    min_confidence=55,
    premium_confidence=70,
    elite_confidence=85,
    max_confidence=98
).process_confidence(df)

df = KillzoneEngine().process_killzones(df)
df = LondonSessionEngine().process_london_session(df)
df = NewYorkSessionEngine().process_newyork_session(df)

df = WeekendGuard(
    friday_cutoff_hour=19,
    monday_resume_hour=10,
    block_weekend=True
).process_weekend_guard(df)

# 2. Profile + symbols
builder = AccountProfileBuilder()
symbol_validator = SymbolValidator()

profile = builder.create_profile(
    client_id="CLIENT_TRADE_MANAGER_TEST_001",
    telegram_user_id="123456",
    account_type="FUNDED",
    balance=10000,
    equity=10000,
    broker="IC Markets",
    prop_firm="FTMO",
    symbol="XAUUSD",
)

broker_symbols = [
    "EURUSD",
    "GBPUSD",
    "XAUUSD",
    "NAS100",
    "US30",
    "BTCUSD",
]

scan = symbol_validator.detect_supported_symbols(broker_symbols)

profile = builder.update_symbols(
    profile=profile,
    detected_symbols=scan.detected_symbols,
    allowed_symbols=scan.allowed_symbols,
    enabled_markets=scan.enabled_markets,
    primary_symbol=scan.primary_symbol,
)

# 3. Entry decisions
entry_manager = EntryManager(
    min_confidence=55,
    min_rr=1.5,
    default_entry_mode="MARKET",
    sl_atr_buffer_mult=0.20,
)

trade_manager = TradeManager(contract_size=100.0)

candidate_rows = df[
    (df["Confidence_Approved"] == True)
    & (
        (df["Session_Trade_Allowed"] == True)
        | (df["London_Trade_Allowed"] == True)
        | (df["NewYork_Trade_Allowed"] == True)
    )
    & (df["Weekend_Trade_Allowed"] == True)
].copy()

print("=" * 70)
print("TRADE MANAGER TEST")
print("=" * 70)

print("\nCandidate setups:", len(candidate_rows))

created = 0

for idx, row in candidate_rows.iterrows():
    decision = entry_manager.build_entry_decision(
        row=row,
        profile=profile,
        current_equity=10000,
        daily_start_equity=10000,
        start_balance=10000,
        peak_equity=10000,
        symbol=profile.primary_symbol,
        entry_mode="MARKET",
    )

    if decision.can_execute:
        trade = trade_manager.create_trade_from_entry(decision)
        trade_manager.open_trade(
            trade_id=trade.trade_id,
            open_time=str(idx),
        )
        created += 1

print("Trades Created:", created)

# 4. Simulate candles after trade open
for trade in trade_manager.get_open_trades():
    open_time = pd.to_datetime(trade.open_time)

    future = df[df.index > open_time].head(80)

    for ts, candle in future.iterrows():
        updated = trade_manager.update_trade_with_candle(
            trade_id=trade.trade_id,
            high=float(candle["High"]),
            low=float(candle["Low"]),
            close=float(candle["Close"]),
            timestamp=str(ts),
        )

        if updated.status in ["TP_HIT", "SL_HIT", "CLOSED", "CANCELLED"]:
            break

result = trade_manager.trades_to_dataframe()

if len(result) > 0:
    result.to_csv(OUT, index=False)

print("\n===== TRADE RESULTS =====")

if len(result) > 0:
    print("Total Trades:", len(result))

    print("\nStatus:")
    print(result["status"].value_counts(dropna=False))

    print("\nClose Reasons:")
    print(result["close_reason"].value_counts(dropna=False))

    print("\nPNL Summary:")
    print("Total PnL Money:", round(result["pnl_money"].sum(), 2))
    print("Average PnL Money:", round(result["pnl_money"].mean(), 2))
    print("Wins:", (result["pnl_money"] > 0).sum())
    print("Losses:", (result["pnl_money"] < 0).sum())

    print("\nTrade Preview:")
    print(
        result[
            [
                "trade_id",
                "symbol",
                "normalized_symbol",
                "market",
                "direction",
                "lot_size",
                "entry_price",
                "stop_loss",
                "take_profit",
                "rr",
                "status",
                "open_time",
                "close_time",
                "close_price",
                "pnl_points",
                "pnl_money",
                "close_reason",
            ]
        ].tail(20)
    )

else:
    print("No trades created.")

print("\nOpen Trades:", len(trade_manager.get_open_trades()))
print("Closed Trades:", len(trade_manager.get_closed_trades()))

print("\n" + "=" * 70)
print(f"Saved: {OUT}")
print("=" * 70)