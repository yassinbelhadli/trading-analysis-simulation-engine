"""Test Simulation Engine across all scenarios."""
import sys; sys.path.insert(0, '.')
import logging
logging.basicConfig(level=logging.WARNING)

from core_engine.simulation import simulate, TradeOutcome


def make_candles(prices):
    candles = []
    for i, c in enumerate(prices):
        candles.append({
            "index": i,
            "time": str(2000 + i),
            "open": c * 0.999,
            "high": c * 1.002,
            "low": c * 0.998,
            "close": c,
            "volume": 100,
        })
    return candles


def snap(entry, sl, tp, direction="BUY"):
    tps = [tp] if isinstance(tp, (int, float)) else tp
    return {
        "metadata": {"symbol": "TEST", "timeframe": "1h"},
        "chart": {"ohlc": []},
        "structure": {},
        "scoring": {"score": 75, "direction": direction},
        "drawing": {"entry_price": entry, "sl_price": sl, "tp": tps, "buy_sell": direction},
        "trade": {"entry_price": entry, "sl_price": sl, "tp_prices": tps, "direction": direction},
    }


def run(label, prices, entry, sl, tp, direction="BUY",
        expected_outcome=None, expected_r=None):
    candles = make_candles(prices)
    s = snap(entry, sl, tp, direction)
    s["chart"]["ohlc"] = candles
    result = simulate(s, candles, entry_idx=0)
    ok = True
    if expected_outcome and result.outcome != expected_outcome:
        print(f"  FAIL {label}: expected {expected_outcome}, got {result.outcome}")
        ok = False
    if expected_r is not None and abs(result.total_r - expected_r) > 0.15:
        print(f"  FAIL {label}: expected {expected_r}R, got {result.total_r}R")
        ok = False
    if ok:
        print(f"  PASS {label}: {result.outcome} {result.total_r}R ({len(result.events)} ev)")
    for ev in result.events:
        r_s = f" rr={ev.rr}" if ev.rr is not None else ""
        print(f"         [{ev.state}] @ {ev.price}: {ev.description}{r_s}")
    return result, ok


all_ok = True

# A) BUY direct TP (risk=1.5, reward=3, RR=2:1)
print("A) BUY direct TP")
r, ok = run("A", [101, 102, 103, 104, 105, 106],
            entry=101, sl=99.5, tp=104, direction="BUY",
            expected_outcome=TradeOutcome.WIN, expected_r=2.0)
all_ok &= ok

# B) BUY direct SL (risk=1.5, price drops below 101.5)
print("\nB) BUY direct SL")
r, ok = run("B", [103, 102, 101, 100, 99],
            entry=103, sl=101.5, tp=106, direction="BUY",
            expected_outcome=TradeOutcome.LOSS, expected_r=-1.0)
all_ok &= ok

# C) Multi-TP: 3 TPs, partials 50/30/20, trailing after TP2
print("\nC) Multi-TP + BE + Trailing")
r, ok = run("C", [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
            entry=101, sl=99.5, tp=[103, 106, 109], direction="BUY",
            expected_outcome=TradeOutcome.WIN)
all_ok &= ok
if r.total_r < 1.5:
    print(f"     Expected >1.5R, got {r.total_r}R")
    all_ok = False

# D) TP1 -> BE -> price reverses to BE
print("\nD) TP1 -> BE -> BE hit")
r, ok = run("D", [101, 102, 103, 104, 103, 102, 101, 100, 99],
            entry=101, sl=99.5, tp=[103, 106], direction="BUY",
            expected_outcome=TradeOutcome.WIN)
all_ok &= ok
if abs(r.total_r - 0.67) > 0.1:
    print(f"     Expected 0.67R, got {r.total_r}R")
    all_ok = False

# E) SELL direct TP
print("\nE) SELL direct TP")
r, ok = run("E", [104, 103, 102, 101, 100, 99],
            entry=104, sl=105.5, tp=101, direction="SELL",
            expected_outcome=TradeOutcome.WIN, expected_r=2.0)
all_ok &= ok

# F) SELL direct SL
print("\nF) SELL direct SL")
r, ok = run("F", [103, 104, 105, 106, 107],
            entry=103, sl=104.5, tp=100, direction="SELL",
            expected_outcome=TradeOutcome.LOSS, expected_r=-1.0)
all_ok &= ok

# G) Entry never reached
print("\nG) Entry not filled")
cg = make_candles([100, 100, 100])
sg = snap(200, 199, 210, "BUY")
sg["chart"]["ohlc"] = cg
rg = simulate(sg, cg, entry_idx=0)
ok_g = rg.outcome in (TradeOutcome.ERROR, TradeOutcome.PENDING)
print(f"  {'PASS' if ok_g else 'FAIL'} G: outcome={rg.outcome}, error={rg.error}")
all_ok &= ok_g

print(f"\n{'='*40}")
print(f"  {'ALL PASSED' if all_ok else 'SOME FAILED'}")
