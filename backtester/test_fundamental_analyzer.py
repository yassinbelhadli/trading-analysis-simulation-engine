import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.fundamental_analyzer import FundamentalAnalyzer

news_file = ROOT / "data" / "processed" / "news_cache.csv"

df = pd.read_csv(news_file)

analyzer = FundamentalAnalyzer()

print("=" * 80)
print("FUNDAMENTAL ANALYZER TEST")
print("=" * 80)

results = []

for _, row in df.iterrows():

    result = analyzer.analyze_row(row)

    results.append(result.to_dict())

    print(
        f"{result.event:35} | "
        f"{result.currency:3} | "
        f"{result.currency_bias:8} | "
        f"{result.xauusd_bias:10} | "
        f"Strength={result.strength:5}"
    )

results_df = pd.DataFrame(results)

save_path = ROOT / "data" / "processed" / "fundamental_analysis.csv"

results_df.to_csv(save_path, index=False)

print()
print("=" * 80)
print("Saved:", save_path)
print("=" * 80)