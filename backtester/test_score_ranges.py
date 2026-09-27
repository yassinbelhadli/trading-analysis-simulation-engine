import pandas as pd
from pathlib import Path

TRADES_FILE = Path("data/processed/XAUUSD_M15_execution_layer_result.csv")

df = pd.read_csv(TRADES_FILE)

df["setup_score"] = pd.to_numeric(df["setup_score"], errors="coerce").fillna(0)
df["pnl_money"] = pd.to_numeric(df["pnl_money"], errors="coerce").fillna(0)

# partial pnl من metadata إذا موجود
import ast

def parse_meta(x):
    try:
        return ast.literal_eval(x) if isinstance(x, str) else {}
    except Exception:
        return {}

def partial_pnl(meta):
    pc = meta.get("partial_close", {}) if isinstance(meta, dict) else {}
    if isinstance(pc, dict):
        return float(pc.get("partial_pnl_money", 0) or 0)
    return 0.0

df["metadata_dict"] = df["metadata"].apply(parse_meta)
df["partial_pnl"] = df["metadata_dict"].apply(partial_pnl)
df["net_pnl"] = df["pnl_money"] + df["partial_pnl"]

df["result_type"] = "LOSS"
df.loc[df["close_reason"] == "TP_HIT", "result_type"] = "WIN"
df.loc[(df["close_reason"] == "SL_HIT") & (df["net_pnl"].abs() <= 0.01), "result_type"] = "BE"
df.loc[df["status"] == "RUNNING", "result_type"] = "RUNNING"

bins = [0, 65, 70, 75, 80, 85, 100]
labels = ["<65", "65-69", "70-74", "75-79", "80-84", "85-100"]

df["score_range"] = pd.cut(
    df["setup_score"],
    bins=bins,
    labels=labels,
    include_lowest=True,
    right=False
)

summary = df.groupby("score_range", observed=False).agg(
    trades=("trade_id", "count"),
    wins=("result_type", lambda x: (x == "WIN").sum()),
    be=("result_type", lambda x: (x == "BE").sum()),
    losses=("result_type", lambda x: (x == "LOSS").sum()),
    running=("result_type", lambda x: (x == "RUNNING").sum()),
    net_pnl=("net_pnl", "sum"),
    avg_score=("setup_score", "mean"),
)

summary["winrate"] = (summary["wins"] / summary["trades"] * 100).round(2)
summary["loss_rate"] = (summary["losses"] / summary["trades"] * 100).round(2)
summary["net_pnl"] = summary["net_pnl"].round(2)
summary["avg_score"] = summary["avg_score"].round(2)

print("=" * 70)
print("SCORE RANGE ANALYSIS")
print("=" * 70)
print(summary)

print("\n===== ENTRY SOURCE BY SCORE RANGE =====")
pivot = df.groupby(["score_range", "entry_source"], observed=False).agg(
    trades=("trade_id", "count"),
    wins=("result_type", lambda x: (x == "WIN").sum()),
    losses=("result_type", lambda x: (x == "LOSS").sum()),
    net_pnl=("net_pnl", "sum"),
)

pivot["winrate"] = (pivot["wins"] / pivot["trades"] * 100).round(2)
pivot["loss_rate"] = (pivot["losses"] / pivot["trades"] * 100).round(2)
pivot["net_pnl"] = pivot["net_pnl"].round(2)

print(pivot)

print("=" * 70)