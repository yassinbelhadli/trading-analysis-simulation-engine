import ast
import pandas as pd
from pathlib import Path

TRADES_FILE = Path("data/processed/XAUUSD_M15_execution_layer_result.csv")

RR_VALUES = [2.0, 2.5, 3.0, 4.0]
CONTRACT_SIZE = 100.0


def parse_meta(x):
    try:
        return ast.literal_eval(x) if isinstance(x, str) else {}
    except Exception:
        return {}


def get_partial_pnl(meta):
    pc = meta.get("partial_close", {}) if isinstance(meta, dict) else {}
    if isinstance(pc, dict):
        return float(pc.get("partial_pnl_money", 0) or 0)
    return 0.0


def simulate_trade(row, rr):
    direction = row["direction"]
    entry = float(row["entry_price"])
    sl = float(row["stop_loss"])
    lot = float(row["lot_size"])

    risk_points = abs(entry - sl)
    if risk_points <= 0:
        return {
            "result": "INVALID",
            "pnl_money": 0.0,
        }

    if direction == "BUY":
        tp = entry + (risk_points * rr)
        highest = float(row["highest_price"])
        lowest = float(row["lowest_price"])

        if lowest <= sl:
            return {
                "result": "SL_HIT",
                "pnl_money": -risk_points * lot * CONTRACT_SIZE,
            }

        if highest >= tp:
            return {
                "result": "TP_HIT",
                "pnl_money": risk_points * rr * lot * CONTRACT_SIZE,
            }

    elif direction == "SELL":
        tp = entry - (risk_points * rr)
        highest = float(row["highest_price"])
        lowest = float(row["lowest_price"])

        if highest >= sl:
            return {
                "result": "SL_HIT",
                "pnl_money": -risk_points * lot * CONTRACT_SIZE,
            }

        if lowest <= tp:
            return {
                "result": "TP_HIT",
                "pnl_money": risk_points * rr * lot * CONTRACT_SIZE,
            }

    return {
        "result": "NO_HIT",
        "pnl_money": 0.0,
    }


def summarize(results_df):
    total = len(results_df)
    wins = int((results_df["result"] == "TP_HIT").sum())
    losses = int((results_df["result"] == "SL_HIT").sum())
    no_hit = int((results_df["result"] == "NO_HIT").sum())

    net_pnl = float(results_df["pnl_money"].sum())
    gross_profit = float(results_df[results_df["pnl_money"] > 0]["pnl_money"].sum())
    gross_loss = abs(float(results_df[results_df["pnl_money"] < 0]["pnl_money"].sum()))

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "no_hit": no_hit,
        "winrate": round((wins / total) * 100, 2) if total else 0.0,
        "loss_rate": round((losses / total) * 100, 2) if total else 0.0,
        "net_pnl": round(net_pnl, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "expectancy": round(net_pnl / total, 2) if total else 0.0,
    }


if not TRADES_FILE.exists():
    raise FileNotFoundError(
        f"Trades file not found: {TRADES_FILE}. Run test_execution_layer.py first."
    )

df = pd.read_csv(TRADES_FILE)

required = [
    "direction",
    "entry_price",
    "stop_loss",
    "lot_size",
    "highest_price",
    "lowest_price",
]

missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"Missing columns: {missing}")

df["highest_price"] = pd.to_numeric(df["highest_price"], errors="coerce").fillna(df["entry_price"])
df["lowest_price"] = pd.to_numeric(df["lowest_price"], errors="coerce").fillna(df["entry_price"])

print("=" * 70)
print("RR COMPARISON TEST")
print("=" * 70)

all_summaries = []

for rr in RR_VALUES:
    rows = []

    for _, row in df.iterrows():
        result = simulate_trade(row, rr)
        rows.append(result)

    results_df = pd.DataFrame(rows)
    summary = summarize(results_df)
    summary["rr"] = rr
    all_summaries.append(summary)

summary_df = pd.DataFrame(all_summaries)

summary_df = summary_df[
    [
        "rr",
        "trades",
        "wins",
        "losses",
        "no_hit",
        "winrate",
        "loss_rate",
        "net_pnl",
        "profit_factor",
        "expectancy",
    ]
]

print(summary_df.to_string(index=False))

OUT = Path("data/processed/XAUUSD_M15_rr_comparison.csv")
summary_df.to_csv(OUT, index=False)

print("=" * 70)
print(f"Saved: {OUT}")
print("=" * 70)