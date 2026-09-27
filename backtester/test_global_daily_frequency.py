import pandas as pd
from pathlib import Path

FILES = [
    ("XAUUSD", Path("data/processed/XAUUSD_M15_execution_layer_result.csv")),
    ("USTEC", Path("data/processed/USTEC_M15_execution_layer_result.csv")),
    ("BTCUSDm", Path("data/processed/BTCUSDm_M15_execution_layer_result.csv")),
]

all_trades = []

for symbol, file in FILES:
    if not file.exists():
        print(f"Missing file: {file}")
        continue

    df = pd.read_csv(file)

    if len(df) == 0:
        continue

    df["symbol_group"] = symbol
    df["open_time"] = pd.to_datetime(df["open_time"], errors="coerce")
    df["trade_date"] = df["open_time"].dt.date

    all_trades.append(df)

if not all_trades:
    raise ValueError("No trades found. Run test_multi_symbol_execution.py first.")

trades = pd.concat(all_trades, ignore_index=True)

daily = trades.groupby("trade_date").agg(
    total_trades=("trade_id", "count"),
    xauusd_trades=("symbol_group", lambda x: (x == "XAUUSD").sum()),
    ustec_trades=("symbol_group", lambda x: (x == "USTEC").sum()),
    btc_trades=("symbol_group", lambda x: (x == "BTCUSDm").sum()),
)

daily = daily.reset_index()

over_5 = daily[daily["total_trades"] > 5].copy()
over_3 = daily[daily["total_trades"] > 3].copy()

print("=" * 70)
print("GLOBAL DAILY TRADE FREQUENCY")
print("=" * 70)

print("Total trades:", len(trades))
print("Total trading days:", len(daily))
print("Average trades/day:", round(daily["total_trades"].mean(), 2))
print("Max trades/day:", int(daily["total_trades"].max()))

print("\n===== DAYS WITH MORE THAN 5 TRADES =====")
if len(over_5) > 0:
    print(over_5.to_string(index=False))
else:
    print("None")

print("\n===== DAYS WITH MORE THAN 3 TRADES =====")
if len(over_3) > 0:
    print(over_3.to_string(index=False))
else:
    print("None")

print("\n===== DAILY DISTRIBUTION =====")
print(daily["total_trades"].value_counts().sort_index())

OUT = Path("data/processed/global_daily_trade_frequency.csv")
daily.to_csv(OUT, index=False)

print("=" * 70)
print(f"Saved: {OUT}")
print("=" * 70)