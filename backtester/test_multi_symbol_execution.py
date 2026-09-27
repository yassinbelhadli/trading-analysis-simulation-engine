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
from core_engine.risk.global_trade_limiter import GlobalDailyTradeLimiter

from core_engine.execution.entry_manager import EntryManager
from core_engine.execution.trade_manager import TradeManager
from core_engine.execution.break_even import BreakEvenManager
from core_engine.execution.partial_close import PartialCloseManager
from core_engine.execution.trailing_stop import TrailingStopManager

from core_engine.filters.htf_bias_filter import HTFBiasFilter
from core_engine.filters.htf_score_modifier import HTFScoreModifier


SYMBOLS = [
    {
        "name": "XAUUSD",
        "file": ROOT / "data" / "raw" / "XAUUSD_M15.csv",
        "profile_symbol": "XAUUSD",
        "contract_size": 100.0,
    },
    {
        "name": "USTEC",
        "file": ROOT / "data" / "raw" / "USTEC_M15.csv",
        "profile_symbol": "NAS100",
        "contract_size": 10.0,
    },
    {
        "name": "BTCUSDm",
        "file": ROOT / "data" / "raw" / "BTCUSDm_M15.csv",
        "profile_symbol": "BTCUSD",
        "contract_size": 1.0,
    },
]


def load_mt5_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")

    df.columns = [
        c.replace("<", "").replace(">", "").strip().title()
        for c in df.columns
    ]

    df.rename(columns={
        "Time": "Clock",
        "Tickvol": "TickVolume",
        "Vol": "Volume",
    }, inplace=True)

    df["Time"] = pd.to_datetime(
        df["Date"].astype(str) + " " + df["Clock"].astype(str),
        errors="coerce"
    )

    df = df[["Time", "Open", "High", "Low", "Close", "TickVolume", "Volume", "Spread"]]
    df.set_index("Time", inplace=True)

    for col in ["Open", "High", "Low", "Close", "TickVolume", "Volume", "Spread"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna()


def process_pipeline(df: pd.DataFrame) -> pd.DataFrame:
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

    return df


def build_profile(symbol_name: str):
    builder = AccountProfileBuilder()

    return builder.create_profile(
        client_id=f"CLIENT_{symbol_name}_TEST",
        telegram_user_id="123456",
        account_type="FUNDED",
        balance=10000,
        equity=10000,
        broker="IC Markets",
        prop_firm="FTMO",
        symbol=symbol_name,
    )


def run_symbol(symbol_cfg, global_limiter):
    name = symbol_cfg["name"]
    data_file = symbol_cfg["file"]
    profile_symbol = symbol_cfg["profile_symbol"]
    contract_size = symbol_cfg["contract_size"]

    out = ROOT / "data" / "processed" / f"{name}_M15_execution_layer_result.csv"
    events_out = ROOT / "data" / "processed" / f"{name}_M15_execution_events.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print(f"MULTI SYMBOL EXECUTION TEST: {name}")
    print("=" * 80)

    if not data_file.exists():
        print(f"FILE NOT FOUND: {data_file}")
        return {
            "symbol": name,
            "status": "FILE_NOT_FOUND",
            "trades": 0,
            "net_pnl": 0,
        }

    df = load_mt5_csv(data_file)
    df = process_pipeline(df)

    candidate_rows = df[
        (df["Confidence_Approved"] == True)
        & (
            (df["Session_Trade_Allowed"] == True)
            | (df["London_Trade_Allowed"] == True)
            | (df["NewYork_Trade_Allowed"] == True)
        )
        & (df["Weekend_Trade_Allowed"] == True)
    ].copy()

    profile = build_profile(profile_symbol)

    entry_manager = EntryManager(
        min_confidence=50,
        min_rr=1.5,
        default_entry_mode="SMART",
        sl_atr_buffer_mult=0.20,
        require_zone_entry=True,
    )

    trade_manager = TradeManager(contract_size=contract_size)

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
        contract_size=contract_size,
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

    events = []
    created = 0

    for idx, row in candidate_rows.iterrows():
        limit_result = global_limiter.evaluate(
            timestamp=idx,
            symbol=name,
            row=row,
        )

        if not limit_result.allowed:
            events.append({
                "time": idx,
                "event": "GLOBAL_ENTRY_REJECTED",
                "reason": limit_result.reason,
                "price": row.get("Close", None),
                "symbol": name,
                "priority_score": limit_result.priority_score,
                "global_daily_count": limit_result.global_daily_count,
                "symbol_daily_count": limit_result.symbol_daily_count,
            })
            continue

        decision = entry_manager.build_entry_decision(
            row=row,
            profile=profile,
            current_equity=10000,
            daily_start_equity=10000,
            start_balance=10000,
            peak_equity=10000,
            symbol=profile_symbol,
            entry_mode="SMART",
        )

        if not decision.can_execute:
            events.append({
                "time": idx,
                "event": "ENTRY_REJECTED",
                "reason": decision.reason,
                "price": row.get("Close", None),
                "symbol": name,
            })
            continue

        trade = trade_manager.create_trade_from_entry(decision)
        trade_manager.open_trade(trade.trade_id, open_time=str(idx))
        created += 1

        global_limiter.register_trade(
            timestamp=idx,
            symbol=name,
        )

        events.append({
            "time": idx,
            "event": "TRADE_OPENED",
            "trade_id": trade.trade_id,
            "price": trade.entry_price,
            "direction": trade.direction,
            "lot_size": trade.lot_size,
            "sl": trade.stop_loss,
            "tp": trade.take_profit,
            "entry_source": trade.entry_source,
            "sl_source": trade.sl_source,
            "symbol": name,
        })

    for trade in list(trade_manager.get_open_trades()):
        open_time = pd.to_datetime(trade.open_time)
        future = df[df.index > open_time].head(120)

        for ts, candle in future.iterrows():
            current_price = float(candle["Close"])

            partial_result = partial_manager.evaluate(trade=trade, current_price=current_price)

            if partial_result.applied:
                events.append({
                    "time": ts,
                    "event": "PARTIAL_CLOSE",
                    "trade_id": trade.trade_id,
                    "price": current_price,
                    "partial_pnl_money": partial_result.partial_pnl_money,
                    "current_r": partial_result.current_r,
                    "symbol": name,
                })

                be_result = be_manager.evaluate(trade=trade, current_price=current_price)
                if be_result.applied:
                    events.append({
                        "time": ts,
                        "event": "BREAK_EVEN_AFTER_PARTIAL",
                        "trade_id": trade.trade_id,
                        "old_sl": be_result.old_stop_loss,
                        "new_sl": be_result.new_stop_loss,
                        "current_r": be_result.current_r,
                        "symbol": name,
                    })
            else:
                be_result = be_manager.evaluate(trade=trade, current_price=current_price)
                if be_result.applied:
                    events.append({
                        "time": ts,
                        "event": "BREAK_EVEN_MOVED",
                        "trade_id": trade.trade_id,
                        "old_sl": be_result.old_stop_loss,
                        "new_sl": be_result.new_stop_loss,
                        "current_r": be_result.current_r,
                        "symbol": name,
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
                    "old_sl": trailing_result.old_stop_loss,
                    "new_sl": trailing_result.new_stop_loss,
                    "current_r": trailing_result.current_r,
                    "symbol": name,
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
                    "symbol": name,
                })
                break

    trades_result = trade_manager.trades_to_dataframe()
    events_result = pd.DataFrame(events)

    if len(trades_result) > 0:
        trades_result.to_csv(out, index=False)

    if len(events_result) > 0:
        events_result.to_csv(events_out, index=False)

    closed_pnl = round(trades_result["pnl_money"].sum(), 2) if len(trades_result) else 0.0

    realized_partial = 0.0
    if len(events_result) > 0 and "partial_pnl_money" in events_result.columns:
        realized_partial = events_result["partial_pnl_money"].fillna(0).sum()

    net_pnl = round(closed_pnl + realized_partial, 2)

    print("Raw candles:", len(df))
    print("Candidate setups:", len(candidate_rows))
    print("Trades created:", created)

    if len(trades_result) > 0:
        print("\nStatus:")
        print(trades_result["status"].value_counts(dropna=False))

        print("\nClose reasons:")
        print(trades_result["close_reason"].value_counts(dropna=False))

        print("\nPNL:")
        print("Closed PnL:", closed_pnl)
        print("Partial PnL:", round(realized_partial, 2))
        print("Net PnL:", net_pnl)

    if len(events_result) > 0 and "event" in events_result.columns:
        print("\nEvent Summary:")
        print(events_result["event"].value_counts(dropna=False).head(10))

    print(f"\nSaved Trades: {out}")
    print(f"Saved Events: {events_out}")

    return {
        "symbol": name,
        "status": "OK",
        "candles": len(df),
        "candidates": len(candidate_rows),
        "trades": created,
        "closed_pnl": closed_pnl,
        "partial_pnl": round(realized_partial, 2),
        "net_pnl": net_pnl,
    }


global_limiter = GlobalDailyTradeLimiter(
    max_global_trades_per_day=5,
    max_symbol_trades_per_day=3,
    min_priority_score=75.0,
)

all_results = []

for symbol_cfg in SYMBOLS:
    result = run_symbol(symbol_cfg, global_limiter)
    all_results.append(result)

summary = pd.DataFrame(all_results)
summary_out = ROOT / "data" / "processed" / "multi_symbol_execution_summary.csv"
summary.to_csv(summary_out, index=False)

print("\n" + "=" * 80)
print("MULTI SYMBOL SUMMARY")
print("=" * 80)
print(summary)
print("=" * 80)
print(f"Saved Summary: {summary_out}")
print("=" * 80)