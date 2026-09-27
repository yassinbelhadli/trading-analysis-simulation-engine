import pandas as pd
from pathlib import Path

TRADES_FILE = Path("data/processed/BTCUSDm_M15_execution_layer_result.csv")
EVENTS_FILE = Path("data/processed/BTCUSDm_M15_execution_events.csv")

if not TRADES_FILE.exists():
    raise FileNotFoundError(
        f"Missing file: {TRADES_FILE}\n"
        "Run first: python backtester/test_multi_symbol_execution.py"
    )

df = pd.read_csv(TRADES_FILE)

df["pnl_money"] = pd.to_numeric(df["pnl_money"], errors="coerce").fillna(0)
df["setup_score"] = pd.to_numeric(df.get("setup_score", 0), errors="coerce").fillna(0)
df["confidence_score"] = pd.to_numeric(df.get("confidence_score", 0), errors="coerce").fillna(0)
df["rr"] = pd.to_numeric(df.get("rr", 0), errors="coerce").fillna(0)

df["result_type"] = "LOSS"
df.loc[df["close_reason"] == "TP_HIT", "result_type"] = "WIN"
df.loc[(df["close_reason"] == "SL_HIT") & (df["pnl_money"].abs() <= 0.01), "result_type"] = "BE"
df.loc[df["status"] == "RUNNING", "result_type"] = "RUNNING"

df["sl_distance"] = (df["entry_price"] - df["stop_loss"]).abs()

print("=" * 70)
print("BTCUSDm DIAGNOSTICS")
print("=" * 70)

print("\n===== BASIC SUMMARY =====")
print("Trades:", len(df))
print("Wins:", int((df["result_type"] == "WIN").sum()))
print("Losses:", int((df["result_type"] == "LOSS").sum()))
print("BE:", int((df["result_type"] == "BE").sum()))
print("Running:", int((df["result_type"] == "RUNNING").sum()))
print("Net PnL:", round(df["pnl_money"].sum(), 2))
print("Winrate:", round((df["result_type"].eq("WIN").sum() / len(df)) * 100, 2) if len(df) else 0)

print("\n===== PNL STATS =====")
print("Average Winner:", round(df[df["pnl_money"] > 0]["pnl_money"].mean(), 2))
print("Average Loser:", round(df[df["pnl_money"] < 0]["pnl_money"].mean(), 2))
print("Largest Winner:", round(df["pnl_money"].max(), 2))
print("Largest Loser:", round(df["pnl_money"].min(), 2))

print("\n===== SCORE STATS =====")
print(df[["setup_score", "confidence_score", "rr", "sl_distance"]].describe())

print("\n===== BY ENTRY SOURCE =====")
print(df.groupby("entry_source").agg(
    trades=("trade_id", "count"),
    wins=("result_type", lambda x: (x == "WIN").sum()),
    losses=("result_type", lambda x: (x == "LOSS").sum()),
    net_pnl=("pnl_money", "sum"),
    avg_pnl=("pnl_money", "mean"),
    avg_score=("setup_score", "mean"),
    avg_conf=("confidence_score", "mean"),
    avg_sl_distance=("sl_distance", "mean"),
))

print("\n===== BY DIRECTION =====")
print(df.groupby("direction").agg(
    trades=("trade_id", "count"),
    wins=("result_type", lambda x: (x == "WIN").sum()),
    losses=("result_type", lambda x: (x == "LOSS").sum()),
    net_pnl=("pnl_money", "sum"),
    avg_pnl=("pnl_money", "mean"),
    avg_score=("setup_score", "mean"),
    avg_conf=("confidence_score", "mean"),
    avg_sl_distance=("sl_distance", "mean"),
))

print("\n===== CLOSE REASONS =====")
print(df["close_reason"].value_counts(dropna=False))

print("\n===== TRADE DETAILS =====")
print(df[[
    "trade_id",
    "direction",
    "entry_source",
    "setup_score",
    "confidence_score",
    "entry_price",
    "stop_loss",
    "take_profit",
    "rr",
    "sl_distance",
    "pnl_money",
    "close_reason",
]].sort_values("pnl_money").to_string(index=False))

if EVENTS_FILE.exists():
    events = pd.read_csv(EVENTS_FILE)

    print("\n===== REJECT REASONS =====")
    if "reason" in events.columns:
        print(events["reason"].value_counts(dropna=False).head(30))

    print("\n===== EVENT COUNTS =====")
    if "event" in events.columns:
        print(events["event"].value_counts(dropna=False))

print("=" * 70)