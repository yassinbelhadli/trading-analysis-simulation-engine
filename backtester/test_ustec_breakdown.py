import pandas as pd

df = pd.read_csv("data/processed/USTEC_M15_execution_layer_result.csv")

df["pnl_money"] = pd.to_numeric(df["pnl_money"], errors="coerce").fillna(0)
df["setup_score"] = pd.to_numeric(df["setup_score"], errors="coerce").fillna(0)
df["confidence_score"] = pd.to_numeric(df["confidence_score"], errors="coerce").fillna(0)

df["result_type"] = "LOSS"
df.loc[df["close_reason"] == "TP_HIT", "result_type"] = "WIN"
df.loc[(df["close_reason"] == "SL_HIT") & (df["pnl_money"].abs() <= 0.01), "result_type"] = "BE"

print("=" * 70)
print("USTEC BREAKDOWN")
print("=" * 70)

print("\nBy Entry Source:")
print(df.groupby("entry_source").agg(
    trades=("trade_id", "count"),
    wins=("result_type", lambda x: (x == "WIN").sum()),
    losses=("result_type", lambda x: (x == "LOSS").sum()),
    avg_pnl=("pnl_money", "mean"),
    net_pnl=("pnl_money", "sum"),
    avg_score=("setup_score", "mean"),
    avg_conf=("confidence_score", "mean"),
))

print("\nBy Direction:")
print(df.groupby("direction").agg(
    trades=("trade_id", "count"),
    wins=("result_type", lambda x: (x == "WIN").sum()),
    losses=("result_type", lambda x: (x == "LOSS").sum()),
    avg_pnl=("pnl_money", "mean"),
    net_pnl=("pnl_money", "sum"),
    avg_score=("setup_score", "mean"),
))

print("\nWorst Trades:")
print(df.sort_values("pnl_money").head(20)[[
    "trade_id", "direction", "entry_source",
    "setup_score", "confidence_score",
    "pnl_money", "close_reason"
]].to_string(index=False))

print("=" * 70)