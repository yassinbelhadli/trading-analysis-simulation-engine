import pandas as pd

df = pd.read_csv(
    "data/processed/USTEC_M15_execution_layer_result.csv"
)

df["win"] = df["close_reason"] == "TP_HIT"

result = df.groupby("entry_source").agg(
    trades=("trade_id", "count"),
    wins=("win", "sum"),
    net_pnl=("pnl_money", "sum"),
)

result["winrate"] = (
    result["wins"] / result["trades"] * 100
).round(2)

print(result.sort_values("net_pnl", ascending=False))