import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.analytics.daily_trade_analyzer import DailyTradeAnalyzer


TRADES_FILE = ROOT / "data" / "processed" / "XAUUSD_M15_execution_layer_result.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_daily_trade_analysis.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)


print("=" * 70)
print("DAILY TRADE ANALYZER TEST")
print("=" * 70)

if not TRADES_FILE.exists():
    raise FileNotFoundError(
        f"Trades file not found: {TRADES_FILE}\n"
        "Run first: python backtester/test_execution_layer.py"
    )

trades_df = pd.read_csv(TRADES_FILE)

analyzer = DailyTradeAnalyzer(be_tolerance=0.01)

daily_df = analyzer.analyze(trades_df)
summary = analyzer.summary(daily_df)

if len(daily_df) > 0:
    daily_df.to_csv(OUT, index=False)

print("\n===== SUMMARY =====")
for key, value in summary.items():
    print(f"{key}: {value}")

print("\n===== DAILY ANALYSIS =====")
if len(daily_df) > 0:
    print(
        daily_df[
            [
                "date",
                "trades_count",
                "tp_wins",
                "be_trades",
                "real_losses",
                "partial_closed",
                "be_moved",
                "closed_pnl",
                "partial_pnl",
                "net_pnl",
                "real_winrate",
                "loss_rate",
                "trade_quality_state",
            ]
        ]
    )
else:
    print("No daily trade data found.")

print("\n" + "=" * 70)
print(f"Saved: {OUT}")
print("=" * 70)