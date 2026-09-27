from pathlib import Path
import pandas as pd

trades = pd.read_csv(
    "data/processed/BTCUSDm_M15_execution_layer_result.csv"
)

print("="*70)
print("BTC ACCEPTED TRADES SCORE DISTRIBUTION")
print("="*70)

print(trades["setup_score"].describe())

print("\n===== SCORE BUCKETS =====")

bins = [0,70,75,80,85,90,100]

print(
    pd.cut(
        trades["setup_score"],
        bins=bins
    ).value_counts().sort_index()
)