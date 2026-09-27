import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.analytics.daily_trade_analyzer import DailyTradeAnalyzer
from core_engine.analytics.overall_performance_analyzer import OverallPerformanceAnalyzer


TRADES_FILE = ROOT / "data" / "processed" / "XAUUSD_M15_execution_layer_result.csv"
DAILY_OUT = ROOT / "data" / "processed" / "XAUUSD_M15_daily_trade_analysis.csv"
OVERALL_OUT = ROOT / "data" / "processed" / "XAUUSD_M15_overall_performance.csv"

OVERALL_OUT.parent.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("OVERALL PERFORMANCE ANALYZER TEST")
print("=" * 70)

if not TRADES_FILE.exists():
    raise FileNotFoundError(
        f"Trades file not found: {TRADES_FILE}\n"
        "Run first: python backtester/test_execution_layer.py"
    )

trades_df = pd.read_csv(TRADES_FILE)

daily_analyzer = DailyTradeAnalyzer(be_tolerance=0.01)
daily_df = daily_analyzer.analyze(trades_df)

if len(daily_df) > 0:
    daily_df.to_csv(DAILY_OUT, index=False)

overall_analyzer = OverallPerformanceAnalyzer()
summary = overall_analyzer.analyze(daily_df)

summary_df = pd.DataFrame([summary])

if len(summary_df) > 0:
    summary_df.to_csv(OVERALL_OUT, index=False)

print("\n===== OVERALL SUMMARY =====")
for key, value in summary.items():
    print(f"{key}: {value}")

print("\n===== DAILY TABLE =====")
if len(daily_df) > 0:
    print(daily_df)
else:
    print("No daily data found.")

print("\n" + "=" * 70)
print(f"Saved Daily: {DAILY_OUT}")
print(f"Saved Overall: {OVERALL_OUT}")
print("=" * 70)