import pandas as pd

df = pd.read_csv(
    "data/processed/USTEC_M15_execution_layer_result.csv"
)

print("\n===== BASIC STATS =====")

print("Trades:", len(df))

print("\nAverage RR:")
print(df["rr"].mean())

print("\nAverage Winner:")
print(
    df[df["pnl_money"] > 0]["pnl_money"].mean()
)

print("\nAverage Loser:")
print(
    df[df["pnl_money"] < 0]["pnl_money"].mean()
)

print("\nLargest Winner:")
print(df["pnl_money"].max())

print("\nLargest Loser:")
print(df["pnl_money"].min())

print("\nDirection:")
print(df["direction"].value_counts())

print("\nEntry Source:")
print(df["entry_source"].value_counts())

print("\nClose Reasons:")
print(df["close_reason"].value_counts())

print("\nAverage Winner:")
print(df[df["pnl_money"] > 0]["pnl_money"].mean())

print("\nAverage Loser:")
print(df[df["pnl_money"] < 0]["pnl_money"].mean())

print("\nLargest Winner:")
print(df["pnl_money"].max())

print("\nLargest Loser:")
print(df["pnl_money"].min())

print("\nAverage RR:")
print(df["rr"].mean())