"""Stability tests: vary key parameters and measure impact on WR / expectancy.

Runs on 1h timeframe only (confirmed dominant). Each parameter is swept
independently while holding others at baseline.

Module-level constants are patched directly — functions reference them
dynamically at call time, so no reloads needed.
"""

import sys; sys.path.insert(0, '.')
import os, csv, logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

import detection.swing as swing_mod
import detection.entry as entry_mod
import detection.mitigation as mit_mod
from backtester.validate_ict_pipeline import run_symbol, compute_stats

BASELINE = {
    "swing_lookback": 5,
    "rr": 2.0,
    "zone_proximity_pct": 0.002,
    "zone_age_candles": 30,
}

SYMBOLS = [
    ("BTCUSD", "15m", 2500),
    ("ETHUSD", "15m", 2500),
    ("XAUUSD", "15m", 2500),
    ("BTCUSD", "1h", 1500),
    ("ETHUSD", "1h", 1500),
    ("XAUUSD", "1h", 1500),
]

def apply_patches(**overrides):
    swing_mod.LOOKBACK = overrides.get("swing_lookback", BASELINE["swing_lookback"])
    entry_mod.ZONE_PROXIMITY_PCT = overrides.get("zone_proximity_pct", BASELINE["zone_proximity_pct"])
    entry_mod.MAX_ZONE_AGE_CANDLES = overrides.get("zone_age_candles", BASELINE["zone_age_candles"])
    entry_mod.RR_RATIO = overrides.get("rr", BASELINE["rr"])
    mit_mod.MAX_ZONE_AGE = overrides.get("max_zone_age", 50)

def run_sweep(param_name: str, values: list) -> list:
    rows = []
    for val in values:
        apply_patches(**{param_name: val})
        all_sigs = []
        for sym, tf, cnt in SYMBOLS:
            sigs = run_symbol(sym, tf, cnt)
            all_sigs.extend(sigs)

        stats = compute_stats(all_sigs, f"{param_name}={val}")
        rows.append({
            "param": param_name,
            "value": val,
            "entries": stats["total_entries"],
            "wins": stats["wins"],
            "losses": stats["losses"],
            "win_rate": stats["win_rate_pct"],
            "profit_factor": stats["profit_factor"],
            "expectancy": round(stats["expectancy"], 3),
        })
        wr_str = f"{stats['win_rate_pct']:.1f}%" if isinstance(stats['win_rate_pct'], (int, float)) else str(stats['win_rate_pct'])
        pf_str = str(stats['profit_factor']) if isinstance(stats['profit_factor'], str) else f"{stats['profit_factor']:.2f}"
        print(f"  {param_name}={val}: {stats['total_entries']} entries, "
              f"{wr_str} WR, {pf_str} PF, {stats['expectancy']:.3f}R exp")
    return rows

if __name__ == "__main__":
    os.makedirs("backtester/reports", exist_ok=True)

    # Baseline first
    print("=== Baseline ===")
    baseline_rows = run_sweep("baseline", [0])

    sweeps = [
        ("swing_lookback",    [3, 7, 10]),
        ("zone_proximity_pct", [0.001, 0.004, 0.008]),
        ("zone_age_candles",   [15, 45, 60]),
    ]

    all_rows = baseline_rows
    for param, values in sweeps:
        print(f"\n=== Sweep: {param} ===")
        rows = run_sweep(param, values)
        all_rows.extend(rows)

    # Restore baseline for future runs
    apply_patches()

    # CSV
    csv_path = "backtester/reports/stability_sweep.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["param","value","entries","wins","losses",
                                          "win_rate","profit_factor","expectancy"])
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nResults saved to {csv_path}")

    # Print table
    print(f"\n{'='*84}")
    print(f"  STABILITY TEST SUMMARY")
    print(f"{'='*84}")
    print(f"  {'Parameter':20s} {'Value':>8s} {'Entries':>8s} {'Wins':>5s} {'Losses':>6s} {'WR%':>7s} {'PF':>7s} {'Exp':>8s}")
    print(f"  {'-'*69}")
    for r in all_rows:
        v = "baseline" if r['param'] == "baseline" else str(r['value'])
        wr_str = f"{r['win_rate']:.1f}" if isinstance(r['win_rate'], (int, float)) else str(r['win_rate'])
        pf = r['profit_factor']
        pf_str = f"{pf:.2f}" if isinstance(pf, (int, float)) else str(pf)
        print(f"  {r['param']:20s} {v:>8s} {r['entries']:>8d} {r['wins']:>5d} {r['losses']:>6d} "
              f"{wr_str:>6s}% {pf_str:>7s} {r['expectancy']:>8.3f}")
