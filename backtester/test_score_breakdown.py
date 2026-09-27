import ast
import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

TRADES_FILE = ROOT / "data" / "processed" / "XAUUSD_M15_execution_layer_result.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_score_breakdown.csv"

df = pd.read_csv(TRADES_FILE)


def parse_meta(x):
    try:
        return ast.literal_eval(x) if isinstance(x, str) else {}
    except Exception:
        return {}


def get_nested(meta, *keys, default=0):
    cur = meta
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


df["metadata_dict"] = df["metadata"].apply(parse_meta)

df["entry_source"] = df["metadata_dict"].apply(lambda m: m.get("entry_source"))
df["sl_source"] = df["metadata_dict"].apply(lambda m: m.get("sl_source"))

df["setup_score"] = df["metadata_dict"].apply(
    lambda m: get_nested(m, "trade_quality", "score", default=0)
)

df["raw_lot_size"] = df["metadata_dict"].apply(
    lambda m: get_nested(m, "trade_quality", "raw_lot_size", default=0)
)

df["sl_distance"] = df["metadata_dict"].apply(
    lambda m: get_nested(m, "trade_quality", "sl_distance", default=0)
)

df["confidence_score"] = 0.0

df["pnl_money"] = pd.to_numeric(df["pnl_money"], errors="coerce").fillna(0)

df["partial_pnl"] = df["metadata_dict"].apply(
    lambda m: get_nested(m, "partial_close", "partial_pnl_money", default=0)
)

df["net_pnl"] = df["pnl_money"] + df["partial_pnl"]

df["result_type"] = "LOSS"
df.loc[df["close_reason"] == "TP_HIT", "result_type"] = "WIN"
df.loc[(df["close_reason"] == "SL_HIT") & (df["net_pnl"].abs() <= 0.01), "result_type"] = "BE"
df.loc[df["status"] == "RUNNING", "result_type"] = "RUNNING"

print("=" * 70)
print("SCORE BREAKDOWN")
print("=" * 70)

print("\n===== RESULT COUNTS =====")
print(df["result_type"].value_counts(dropna=False))

print("\n===== SCORE BY RESULT =====")
print(
    df.groupby("result_type")[["setup_score", "sl_distance", "raw_lot_size", "net_pnl"]]
    .agg(["count", "mean", "min", "max"])
)

print("\n===== ENTRY SOURCE SUMMARY =====")
entry_summary = df.groupby("entry_source").agg(
    trades=("trade_id", "count"),
    wins=("result_type", lambda x: (x == "WIN").sum()),
    be=("result_type", lambda x: (x == "BE").sum()),
    losses=("result_type", lambda x: (x == "LOSS").sum()),
    running=("result_type", lambda x: (x == "RUNNING").sum()),
    net_pnl=("net_pnl", "sum"),
    avg_score=("setup_score", "mean"),
    avg_sl_distance=("sl_distance", "mean"),
    avg_raw_lot=("raw_lot_size", "mean"),
).reset_index()

entry_summary["winrate"] = (entry_summary["wins"] / entry_summary["trades"] * 100).round(2)
entry_summary["loss_rate"] = (entry_summary["losses"] / entry_summary["trades"] * 100).round(2)
entry_summary["net_pnl"] = entry_summary["net_pnl"].round(2)

print(entry_summary.sort_values("net_pnl", ascending=False))

print("\n===== DIRECTION SUMMARY =====")
dir_summary = df.groupby("direction").agg(
    trades=("trade_id", "count"),
    wins=("result_type", lambda x: (x == "WIN").sum()),
    be=("result_type", lambda x: (x == "BE").sum()),
    losses=("result_type", lambda x: (x == "LOSS").sum()),
    running=("result_type", lambda x: (x == "RUNNING").sum()),
    net_pnl=("net_pnl", "sum"),
    avg_score=("setup_score", "mean"),
    avg_sl_distance=("sl_distance", "mean"),
).reset_index()

dir_summary["winrate"] = (dir_summary["wins"] / dir_summary["trades"] * 100).round(2)
dir_summary["loss_rate"] = (dir_summary["losses"] / dir_summary["trades"] * 100).round(2)
dir_summary["net_pnl"] = dir_summary["net_pnl"].round(2)

print(dir_summary)

print("\n===== WORST TRADES =====")
print(
    df.sort_values("net_pnl").head(20)[[
        "trade_id",
        "direction",
        "entry_source",
        "sl_source",
        "setup_score",
        "sl_distance",
        "raw_lot_size",
        "close_reason",
        "pnl_money",
        "partial_pnl",
        "net_pnl",
    ]]
)

print("\n===== BEST TRADES =====")
print(
    df.sort_values("net_pnl", ascending=False).head(20)[[
        "trade_id",
        "direction",
        "entry_source",
        "sl_source",
        "setup_score",
        "sl_distance",
        "raw_lot_size",
        "close_reason",
        "pnl_money",
        "partial_pnl",
        "net_pnl",
    ]]
)

entry_summary.to_csv(OUT, index=False)

print("\n" + "=" * 70)
print(f"Saved: {OUT}")
print("=" * 70)