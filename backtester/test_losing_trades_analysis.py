import pandas as pd

df = pd.read_csv(
    "data/processed/XAUUSD_M15_execution_layer_result.csv"
)

losses = df[
    df["close_reason"] == "SL_HIT"
]

print("="*60)
print("LOSING TRADES ANALYSIS")
print("="*60)

print(losses.groupby("entry_source").size())

print("\nDirection:")
print(losses.groupby("direction").size())

print("\nScore Stats:")
print(losses["setup_score"].describe())

print("\nWorst Losses:")
print(
    losses.sort_values("pnl_money")
    [["trade_id","direction","entry_source",
      "setup_score","confidence_score",
      "pnl_money"]]
    .head(20)
)