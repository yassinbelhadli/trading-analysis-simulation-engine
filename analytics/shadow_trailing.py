"""
Shadow-trailing simulation — 100% read-only analytics.
Replays each closed strategic trade and compares actual outcome vs
3 trailing strategies without touching execution or database.

Strategies:
  A. TRAIL_AT_1R        — trail SL behind price by 1R once +1R profit reached
  B. TRAIL_AFTER_PARTIAL — activate trailing on the runner after partial close
  C. STRUCTURE_TRAIL     — trail SL to nearest swing low/high (uses available
                           trade-level extremes; NOT_SIMULATED if data missing)

Available data (read-only):
  entry_price, stop_loss, take_profit, direction, lot_size
  highest_price, lowest_price  (overall MFE/MAE excursion)
  post_partial_highest_price, post_partial_lowest_price
  partial_closed, partial_price, partial_pnl
  realized_pnl, realized_r, close_reason
"""
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

logger = logging.getLogger("shadow_trailing")


TRAIL_DISTANCE_R = 1.0  # trail distance in R multiples


def _r_distance(entry: float, sl: float) -> float:
    return abs(entry - sl)


def _pnl(direction: str, entry: float, exit_price: float, lot: float) -> float:
    if direction.upper() in ("BUY", "LONG"):
        return (exit_price - entry) * lot
    return (entry - exit_price) * lot


def simulate_one(
    trade_id: str,
    entry: float,
    sl: float,
    tp: float,
    direction: str,
    lot: float,
    high: float,
    low: float,
    close_reason: str,
    realized_pnl: float,
    realized_r: Optional[float],
    risk_usd: Optional[float],
    partial_closed: bool = False,
    partial_price: Optional[float] = None,
    partial_pnl: float = 0.0,
    post_high: Optional[float] = None,
    post_low: Optional[float] = None,
) -> dict:
    """Run 3 shadow trailing simulations on a single trade. Returns a dict."""

    risk_dist = _r_distance(entry, sl)
    initial_risk = risk_usd or (risk_dist * lot)
    first_r = entry + risk_dist if direction.upper() in ("BUY", "LONG") else entry - risk_dist
    trail_dist = risk_dist * TRAIL_DISTANCE_R

    actual = {
        "realized_pnl": round(realized_pnl, 2),
        "realized_r": round(realized_r, 4) if realized_r is not None else None,
        "exit_reason": close_reason,
    }

    # ──────────────────────────────────────────────
    # A. TRAIL_AT_1R
    # ──────────────────────────────────────────────
    # Did price reach +1R?
    reached_1r = (direction.upper() in ("BUY", "LONG") and high >= first_r) or \
                 (direction.upper() in ("SELL", "SHORT") and low <= first_r)

    if not reached_1r:
        at_1r = actual.copy()
        at_1r["exit_price"] = None  # no trail activation possible
        at_1r["status"] = "NOT_ACTIVATED"
    else:
        # trail activates; determine where trail SL would be at MFE peak
        if direction.upper() in ("BUY", "LONG"):
            trail_sl = max(entry, high - trail_dist)
            sl_hit = low <= trail_sl
            exit_price = trail_sl if sl_hit else (tp if high >= tp else None)
            reason = "SL_HIT" if sl_hit else ("TP_HIT" if high >= tp else close_reason)
        else:
            trail_sl = min(entry, low + trail_dist)
            sl_hit = high >= trail_sl
            exit_price = trail_sl if sl_hit else (tp if low <= tp else None)
            reason = "SL_HIT" if sl_hit else ("TP_HIT" if low <= tp else close_reason)

        if exit_price is None:
            exit_price = (tp if direction.upper() in ("BUY", "LONG") else tp)

        sim_pnl = _pnl(direction, entry, exit_price, lot)
        sim_r = sim_pnl / initial_risk if initial_risk > 0 else 0.0
        at_1r = {
            "exit_price": round(exit_price, 5),
            "realized_pnl": round(sim_pnl, 2),
            "realized_r": round(sim_r, 4),
            "exit_reason": reason,
            "status": "ACTIVATED",
        }

    # ──────────────────────────────────────────────
    # B. TRAIL_AFTER_PARTIAL
    # ──────────────────────────────────────────────
    if not partial_closed or partial_price is None:
        after_partial = {"status": "NO_PARTIAL"}
    else:
        remaining_lot = lot * (1.0 - partial_closed)  # partial_closed is fraction (e.g. 0.5)
        pp_high = post_high if post_high is not None else high
        pp_low = post_low if post_low is not None else low

        if direction.upper() in ("BUY", "LONG"):
            trail_sl = max(entry, pp_high - trail_dist)
            sl_hit = pp_low <= trail_sl
            exit_price = trail_sl if sl_hit else (tp if pp_high >= tp else None)
            reason = "SL_HIT" if sl_hit else ("TP_HIT" if pp_high >= tp else close_reason)
        else:
            trail_sl = min(entry, pp_low + trail_dist)
            sl_hit = pp_high >= trail_sl
            exit_price = trail_sl if sl_hit else (tp if pp_low <= tp else None)
            reason = "SL_HIT" if sl_hit else ("TP_HIT" if pp_low <= tp else close_reason)

        if exit_price is None:
            exit_price = tp

        runner_pnl = _pnl(direction, entry, exit_price, remaining_lot)
        sim_pnl = partial_pnl + runner_pnl
        sim_r = sim_pnl / initial_risk if initial_risk > 0 else 0.0
        after_partial = {
            "exit_price": round(exit_price, 5),
            "realized_pnl": round(sim_pnl, 2),
            "realized_r": round(sim_r, 4),
            "exit_reason": reason,
            "status": "ACTIVATED",
        }

    # ──────────────────────────────────────────────
    # C. STRUCTURE_TRAIL
    # ──────────────────────────────────────────────
    # Requires OHLC data to detect genuine swing highs/lows.
    # Not stored per trade → NOT_SIMULATED until historical OHLC is available.
    structure = {"status": "NOT_SIMULATED", "reason": "OHLC swing data not available per trade"}

    return {
        "trade_id": trade_id,
        "actual": actual,
        "trail_at_1r": at_1r,
        "trail_after_partial": after_partial,
        "structure_trail": structure,
    }


def simulate_shadow(trades: list[Any]) -> list[dict]:
    results = []
    for t in trades:
        if t.close_reason not in ("TP_HIT", "SL_HIT"):
            continue
        high = t.highest_price or t.entry_price
        low = t.lowest_price or t.entry_price
        post_high = getattr(t, "post_partial_highest_price", None)
        post_low = getattr(t, "post_partial_lowest_price", None)
        partial_closed_frac = 0.5 if t.partial_closed else 0.0  # PARTIAL_CLOSE_PCT is 50%
        results.append(simulate_one(
            trade_id=str(t.id),
            entry=t.entry_price,
            sl=t.stop_loss,
            tp=t.take_profit,
            direction=t.direction,
            lot=t.lot_size,
            high=high,
            low=low,
            close_reason=t.close_reason,
            realized_pnl=t.realized_pnl,
            realized_r=t.realized_r,
            risk_usd=t.initial_risk_usd,
            partial_closed=t.partial_closed or False,
            partial_price=t.partial_price,
            partial_pnl=t.partial_pnl or 0.0,
            post_high=post_high,
            post_low=post_low,
        ))
        # attach trade ids for SummaryResult later
        results[-1]["_symbol"] = t.symbol
        results[-1]["_direction"] = t.direction
    return results


def _profit_factor(pnl_list: list[float]) -> float:
    gross_win = sum(p for p in pnl_list if p > 0)
    gross_loss = abs(sum(p for p in pnl_list if p < 0))
    if gross_loss == 0:
        return float("inf") if gross_win > 0 else 0.0
    return round(gross_win / gross_loss, 4)


def build_summary(results: list[dict]) -> dict:
    sample_size = len(results)
    if sample_size == 0:
        return {"sample_size": 0}

    actual_pnls = [r["actual"]["realized_pnl"] for r in results]
    actual_rs = [r["actual"]["realized_r"] for r in results if r["actual"]["realized_r"] is not None]

    def strategy_stats(key: str) -> dict:
        pnls = []
        rs = []
        not_simulated = 0
        for r in results:
            v = r.get(key, {})
            status = v.get("status")
            if status in ("NOT_SIMULATED", "NOT_ACTIVATED", "NO_PARTIAL") or status is None:
                pnls.append(r["actual"]["realized_pnl"])
                ar = r["actual"]["realized_r"]
                if ar is not None:
                    rs.append(ar)
                if status == "NOT_SIMULATED":
                    not_simulated += 1
            else:
                pnls.append(v["realized_pnl"])
                vr = v.get("realized_r")
                if vr is not None:
                    rs.append(vr)

        net = round(sum(pnls), 2)
        avg_r_val = round(sum(rs) / len(rs), 4) if rs else None
        result = {
            "net_pnl": net,
            "profit_factor": _profit_factor(pnls),
            "avg_r": avg_r_val,
        }
        if not_simulated == len(results):
            return {
                "status": "UNAVAILABLE",
                "reason": "OHLC swing data not available per trade",
                "sample_size": 0,
            }
        if not_simulated:
            result["not_simulated"] = not_simulated
        return result

    confidence = "LOW"
    min_rec = 50
    if sample_size >= 100:
        confidence = "HIGH"
        min_rec = 100
    elif sample_size >= 50:
        confidence = "MEDIUM"
        min_rec = 50

    return {
        "sample_size": sample_size,
        "confidence": confidence,
        "minimum_recommended_sample": min_rec,
        "actual": {
            "net_pnl": round(sum(actual_pnls), 2),
            "profit_factor": _profit_factor(actual_pnls),
            "avg_r": round(sum(actual_rs) / len(actual_rs), 4) if actual_rs else 0.0,
        },
        "trail_at_1r": strategy_stats("trail_at_1r"),
        "trail_after_partial": strategy_stats("trail_after_partial"),
        "structure_trail": strategy_stats("structure_trail"),
    }


def export_shadow(results: list[dict], out_dir: str | Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Strip internal fields before export
    clean = []
    for r in results:
        r_clean = {k: v for k, v in r.items() if not k.startswith("_")}
        clean.append(r_clean)

    path = out_dir / "shadow_trailing.json"
    path.write_text(json.dumps(clean, indent=2, default=str), encoding="utf-8")
    logger.info("Shadow trailing results written to %s", path)

    summary = build_summary(results)
    spath = out_dir / "shadow_trailing_summary.json"
    spath.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Shadow trailing summary written to %s", spath)

    # CSV comparison table
    import csv
    csv_path = out_dir / "shadow_trailing_comparison.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["trade_id", "symbol", "direction",
                     "actual_pnl", "actual_r", "actual_reason",
                     "trail_at_1r_pnl", "trail_at_1r_r", "trail_at_1r_reason", "trail_at_1r_status",
                     "trail_after_partial_pnl", "trail_after_partial_r", "trail_after_partial_reason", "trail_after_partial_status",
                     "structure_pnl", "structure_r", "structure_reason", "structure_status"])
        for r in results:
            a = r["actual"]
            t1 = r.get("trail_at_1r", {})
            t2 = r.get("trail_after_partial", {})
            t3 = r.get("structure_trail", {})
            w.writerow([
                r.get("trade_id", ""), r.get("_symbol", ""), r.get("_direction", ""),
                a.get("realized_pnl"), a.get("realized_r"), a.get("exit_reason"),
                t1.get("realized_pnl"), t1.get("realized_r"), t1.get("exit_reason"), t1.get("status"),
                t2.get("realized_pnl"), t2.get("realized_r"), t2.get("exit_reason"), t2.get("status"),
                t3.get("realized_pnl"), t3.get("realized_r"), t3.get("exit_reason"), t3.get("status"),
            ])
    logger.info("Shadow trailing CSV written to %s", csv_path)

    return [path, spath, csv_path]
