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
from core_engine.execution.break_even import BreakEvenManager
from core_engine.execution.partial_close import PartialCloseManager
from core_engine.execution.trailing_stop import TrailingStopManager

from core_engine.filters.htf_bias_filter import HTFBiasFilter
from core_engine.filters.htf_score_modifier import HTFScoreModifier


DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_execution_layer_result.csv"
EVENTS_OUT = ROOT / "data" / "processed" / "XAUUSD_M15_execution_events.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA, sep="\t")

df.columns = [
    c.replace("<", "").replace(">", "").strip().title()
    for c in df.columns
]

df.rename(columns={
    "Date": "Date",
    "Time": "Clock",
    "Open": "Open",
    "High": "High",
    "Low": "Low",
    "Close": "Close",
    "Tickvol": "TickVolume",
    "Vol": "Volume",
    "Spread": "Spread",
}, inplace=True)

df["Time"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Clock"].astype(str))

df = df[["Time", "Open", "High", "Low", "Close", "TickVolume", "Volume", "Spread"]]
df.set_index("Time", inplace=True)

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
    min_score=68,
    premium_score=80,
    max_daily_setups=3,
    min_daily_setups_target=1,
    cooldown_candles=12,
    max_same_direction_per_day=1,
    require_mss_or_choch=False,
    require_liquidity=True,
    require_fvg_or_ob=True,
    prefer_best_setups=True
).process_rankings(df)

df = ConfidenceScoreEngine(
    min_confidence=50,
    premium_confidence=70,
    elite_confidence=85,
    max_confidence=98
).process_confidence(df)

df = HTFScoreModifier(
    aligned_bonus=5.0,
    opposite_penalty=8.0,
    neutral_modifier=0.0,
    score_column="Setup_Score",
    output_column="Setup_Score",
).process_htf_score(df)

df = HTFBiasFilter(
    htf_timeframe="1h",
    swing_left=2,
    swing_right=2,
    bos_buffer_atr_mult=0.10,
    require_htf_bias=True,
    allow_neutral=True,
).process_htf_bias(df)

df = KillzoneEngine().process_killzones(df)
df = LondonSessionEngine().process_london_session(df)
df = NewYorkSessionEngine().process_newyork_session(df)

df = WeekendGuard(
    friday_cutoff_hour=19,
    monday_resume_hour=10,
    block_weekend=True
).process_weekend_guard(df)

candidate_rows = df[
    (df["Confidence_Approved"] == True)
    & (
        (df["Session_Trade_Allowed"] == True)
        | (df["London_Trade_Allowed"] == True)
        | (df["NewYork_Trade_Allowed"] == True)
    )
    & (df["Weekend_Trade_Allowed"] == True)
].copy()

builder = AccountProfileBuilder()
symbol_validator = SymbolValidator()

profile = builder.create_profile(
    client_id="CLIENT_EXECUTION_TEST_001",
    telegram_user_id="123456",
    account_type="FUNDED",
    balance=10000,
    equity=10000,
    broker="IC Markets",
    prop_firm="FTMO",
    symbol="XAUUSD",
)

scan = symbol_validator.detect_supported_symbols(
    broker_symbols=["EURUSD", "GBPUSD", "XAUUSD", "NAS100", "US30", "BTCUSD"],
    prefer_gold_first=True
)

profile = builder.update_symbols(
    profile=profile,
    detected_symbols=scan.detected_symbols,
    allowed_symbols=scan.allowed_symbols,
    enabled_markets=scan.enabled_markets,
    primary_symbol=scan.primary_symbol,
)

entry_manager = EntryManager(
    min_confidence=50,
    min_rr=1.5,
    default_entry_mode="SMART",
    sl_atr_buffer_mult=0.20,
    require_zone_entry=True,
)

trade_manager = TradeManager(contract_size=100.0)

be_manager = BreakEvenManager(
    trigger_r=1.0,
    lock_profit_points=0.0,
    only_once=True
)

partial_manager = PartialCloseManager(
    trigger_r=0.75,
    close_percent=50.0,
    min_remaining_lot=0.01,
    lot_step=0.01,
    contract_size=100.0,
    only_once=True
)

trailing_manager = TrailingStopManager(
    trigger_r=2.0,
    trailing_method="HYBRID",
    atr_mult=1.5,
    swing_buffer_atr_mult=0.20,
    min_sl_improvement=0.01,
    only_after_be=True
)

print("=" * 70)
print("EXECUTION LAYER FULL TEST")
print("=" * 70)
print("Candidate setups:", len(candidate_rows))

created = 0
events = []

for idx, row in candidate_rows.iterrows():
    decision = entry_manager.build_entry_decision(
        row=row,
        profile=profile,
        current_equity=10000,
        daily_start_equity=10000,
        start_balance=10000,
        peak_equity=10000,
        symbol=profile.primary_symbol,
        entry_mode="SMART",
    )

    if not decision.can_execute:
        events.append({
            "time": idx,
            "event": "ENTRY_REJECTED",
            "trade_id": None,
            "reason": decision.reason,
            "price": row.get("Close", None),
            "entry_source": decision.metadata.get("entry_source"),
            "sl_source": decision.metadata.get("sl_source"),
        })
        continue

    trade = trade_manager.create_trade_from_entry(decision)
    trade_manager.open_trade(trade_id=trade.trade_id, open_time=str(idx))
    created += 1

    events.append({
        "time": idx,
        "event": "TRADE_OPENED",
        "trade_id": trade.trade_id,
        "reason": "TRADE_READY",
        "price": trade.entry_price,
        "direction": trade.direction,
        "lot_size": trade.lot_size,
        "sl": trade.stop_loss,
        "tp": trade.take_profit,
        "entry_source": decision.metadata.get("entry_source"),
        "sl_source": decision.metadata.get("sl_source"),
    })

for trade in list(trade_manager.get_open_trades()):
    open_time = pd.to_datetime(trade.open_time)
    future = df[df.index > open_time].head(120)

    for ts, candle in future.iterrows():
        current_price = float(candle["Close"])

        partial_result = partial_manager.evaluate(
            trade=trade,
            current_price=current_price
        )

        if partial_result.applied:
            events.append({
                "time": ts,
                "event": "PARTIAL_CLOSE",
                "trade_id": trade.trade_id,
                "reason": partial_result.reason,
                "price": current_price,
                "closed_lot": partial_result.closed_lot_size,
                "remaining_lot": partial_result.remaining_lot_size,
                "partial_pnl_money": partial_result.partial_pnl_money,
                "current_r": partial_result.current_r,
            })

            be_result_after_partial = be_manager.evaluate(
                trade=trade,
                current_price=current_price
            )

            if be_result_after_partial.applied:
                events.append({
                    "time": ts,
                    "event": "BREAK_EVEN_AFTER_PARTIAL",
                    "trade_id": trade.trade_id,
                    "reason": be_result_after_partial.reason,
                    "price": current_price,
                    "old_sl": be_result_after_partial.old_stop_loss,
                    "new_sl": be_result_after_partial.new_stop_loss,
                    "current_r": be_result_after_partial.current_r,
                })

        else:
            be_result = be_manager.evaluate(
                trade=trade,
                current_price=current_price
            )

            if be_result.applied:
                events.append({
                    "time": ts,
                    "event": "BREAK_EVEN_MOVED",
                    "trade_id": trade.trade_id,
                    "reason": be_result.reason,
                    "price": current_price,
                    "old_sl": be_result.old_stop_loss,
                    "new_sl": be_result.new_stop_loss,
                    "current_r": be_result.current_r,
                })

        trailing_result = trailing_manager.evaluate(
            trade=trade,
            current_price=current_price,
            row=candle
        )

        if trailing_result.applied:
            events.append({
                "time": ts,
                "event": "TRAILING_STOP_MOVED",
                "trade_id": trade.trade_id,
                "reason": trailing_result.reason,
                "price": current_price,
                "old_sl": trailing_result.old_stop_loss,
                "new_sl": trailing_result.new_stop_loss,
                "current_r": trailing_result.current_r,
                "method": trailing_result.trailing_method,
            })

        updated = trade_manager.update_trade_with_candle(
            trade_id=trade.trade_id,
            high=float(candle["High"]),
            low=float(candle["Low"]),
            close=float(candle["Close"]),
            timestamp=str(ts),
        )

        if updated.status in ["TP_HIT", "SL_HIT", "CLOSED", "CANCELLED"]:
            events.append({
                "time": ts,
                "event": "TRADE_CLOSED",
                "trade_id": updated.trade_id,
                "reason": updated.close_reason,
                "price": updated.close_price,
                "pnl_money": updated.pnl_money,
                "pnl_points": updated.pnl_points,
                "status": updated.status,
            })
            break

trades_result = trade_manager.trades_to_dataframe()
events_result = pd.DataFrame(events)

if len(trades_result) > 0:
    trades_result.to_csv(OUT, index=False)

if len(events_result) > 0:
    events_result.to_csv(EVENTS_OUT, index=False)

print("\n===== EXECUTION RESULTS =====")
print("Trades Created:", created)

if len(trades_result) > 0:
    print("Total Trades:", len(trades_result))

    print("\nStatus:")
    print(trades_result["status"].value_counts(dropna=False))

    print("\nClose Reasons:")
    print(trades_result["close_reason"].value_counts(dropna=False))

    print("\nBE moved:")
    print(trades_result["be_moved"].value_counts(dropna=False))

    print("\nPartial closed:")
    print(trades_result["partial_closed"].value_counts(dropna=False))

    print("\nTrailing active:")
    print(trades_result["trailing_active"].value_counts(dropna=False))

    realized_partial = 0.0
    for _, t in trades_result.iterrows():
        meta = t.get("metadata", {})
        if isinstance(meta, dict) and "partial_close" in meta:
            realized_partial += float(meta["partial_close"].get("partial_pnl_money", 0))

    closed_pnl = round(trades_result["pnl_money"].sum(), 2)
    net_pnl = round(closed_pnl + realized_partial, 2)

    print("\nPNL:")
    print("Closed PnL Money:", closed_pnl)
    print("Realized Partial PnL:", round(realized_partial, 2))
    print("Net Approx PnL:", net_pnl)

    print("\nTrade Preview:")
    print(
        trades_result[
            [
                "trade_id",
                "symbol",
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
                "pnl_money",
                "be_moved",
                "partial_closed",
                "trailing_active",
                "close_reason",
            ]
        ]
    )
else:
    print("No trades created.")

print("\n===== EXECUTION EVENTS =====")
if len(events_result) > 0:
    print("Events:", len(events_result))
    print(events_result["event"].value_counts(dropna=False))
    print("\nEvents Preview:")
    print(events_result.tail(50))
else:
    print("No events generated.")

print("\nOpen Trades:", len(trade_manager.get_open_trades()))
print("Closed Trades:", len(trade_manager.get_closed_trades()))

print("\n" + "=" * 70)
print(f"Saved Trades: {OUT}")
print(f"Saved Events: {EVENTS_OUT}")
print("=" * 70)