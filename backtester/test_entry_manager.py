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


DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_entry_manager_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)
df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

# 1. Detection pipeline
df = MarketStructureDetector().process_structure(df)
df = LiquidityEngine().process_liquidity(df)
df = FVGDetector().process_fvg(df)
df = OrderBlockEngine().process_order_blocks(df)
df = VolumeImbalanceDetector().process_volume_imbalance(df)
df = LiquidityVoidDetector().process_liquidity_void(df)
df = PremiumDiscountDetector().process_premium_discount(df)
df = SupportResistanceDetector().process_support_resistance(df)
df = CandlePatternDetector().process_candle_patterns(df)

# 2. Scoring pipeline
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

# 3. Sessions
df = KillzoneEngine().process_killzones(df)
df = LondonSessionEngine().process_london_session(df)
df = NewYorkSessionEngine().process_newyork_session(df)

# 4. Weekend guard
df = WeekendGuard(
    friday_cutoff_hour=19,
    monday_resume_hour=10,
    block_weekend=True
).process_weekend_guard(df)

# 5. Account profile + broker symbol scan
builder = AccountProfileBuilder()
symbol_validator = SymbolValidator()

profile = builder.create_profile(
    client_id="CLIENT_ENTRY_TEST_001",
    telegram_user_id="123456",
    account_type="FUNDED",
    balance=10000,
    equity=10000,
    broker="IC Markets",
    prop_firm="FTMO",
    symbol="XAUUSD",
)

# Simulated broker symbols from MT5
broker_symbols = [
    "EURUSD",
    "GBPUSD",
    "XAUUSD",
    "NAS100",
    "US30",
    "BTCUSD",
]

symbol_scan = symbol_validator.detect_supported_symbols(
    broker_symbols=broker_symbols,
    prefer_gold_first=True
)

profile = builder.update_symbols(
    profile=profile,
    detected_symbols=symbol_scan.detected_symbols,
    allowed_symbols=symbol_scan.allowed_symbols,
    enabled_markets=symbol_scan.enabled_markets,
    primary_symbol=symbol_scan.primary_symbol,
)

print("=" * 70)
print("ENTRY MANAGER TEST")
print("=" * 70)

print("\n===== SYMBOL SCAN =====")
print(symbol_scan.to_dict())
print(symbol_validator.generate_telegram_message(symbol_scan))

print("\n===== PROFILE =====")
print(builder.profile_summary(profile))

# 6. Entry manager
entry_manager = EntryManager(
    min_confidence=55,
    min_rr=1.5,
    default_entry_mode="MARKET",
    sl_atr_buffer_mult=0.20,
)

current_equity = 10000
daily_start_equity = 10000
start_balance = 10000
peak_equity = 10000

decisions = []

candidate_rows = df[
    (df["Confidence_Approved"] == True)
    & (
        (df["Session_Trade_Allowed"] == True)
        | (df["London_Trade_Allowed"] == True)
        | (df["NewYork_Trade_Allowed"] == True)
    )
    & (df["Weekend_Trade_Allowed"] == True)
].copy()

print("\n===== CANDIDATES =====")
print("Candidate setups:", len(candidate_rows))

for idx, row in candidate_rows.iterrows():
    decision = entry_manager.build_entry_decision(
        row=row,
        profile=profile,
        current_equity=current_equity,
        daily_start_equity=daily_start_equity,
        start_balance=start_balance,
        peak_equity=peak_equity,
        symbol=profile.primary_symbol,
        entry_mode="MARKET",
    )

    d = decision.to_dict()
    d["Time"] = idx
    decisions.append(d)

result = pd.DataFrame(decisions)

if len(result) > 0:
    result.set_index("Time", inplace=True)
    result.to_csv(OUT)

print("\n===== ENTRY DECISIONS =====")

if len(result) > 0:
    print("Total Decisions:", len(result))
    print("Can Execute:", result["can_execute"].sum())

    print("\nReasons:")
    print(result["reason"].value_counts(dropna=False))

    print("\nMarkets:")
    print(result["market"].value_counts(dropna=False))

    print("\nDirections:")
    print(result["direction"].value_counts(dropna=False))

    print("\nTrade Preview:")
    print(
        result[
            [
                "symbol",
                "normalized_symbol",
                "market",
                "direction",
                "entry_type",
                "entry_price",
                "stop_loss",
                "take_profit",
                "rr",
                "lot_size",
                "risk_amount",
                "actual_risk_amount",
                "actual_risk_percent",
                "confidence_score",
                "setup_score",
                "session_name",
                "killzone",
                "reason",
                "setup_id",
            ]
        ].tail(20)
    )

else:
    print("No entry decisions generated.")

print("\n===== SAFETY TESTS =====")

if len(candidate_rows) > 0:
    sample_row = candidate_rows.iloc[-1]

    bad_symbol_decision = entry_manager.build_entry_decision(
        row=sample_row,
        profile=profile,
        current_equity=current_equity,
        daily_start_equity=daily_start_equity,
        start_balance=start_balance,
        peak_equity=peak_equity,
        symbol="EURUSD",
        entry_mode="MARKET",
    )

    print("\nBad Symbol Test:")
    print(bad_symbol_decision.to_dict())

    bad_equity_decision = entry_manager.build_entry_decision(
        row=sample_row,
        profile=profile,
        current_equity=9050,
        daily_start_equity=10000,
        start_balance=10000,
        peak_equity=10100,
        symbol=profile.primary_symbol,
        entry_mode="MARKET",
    )

    print("\nBad Drawdown Test:")
    print(bad_equity_decision.to_dict())

print("\n" + "=" * 70)
print(f"Saved: {OUT}")
print("=" * 70)