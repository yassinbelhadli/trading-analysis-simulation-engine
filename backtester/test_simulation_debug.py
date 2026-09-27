"""Debug simulation — trace lifecycle step by step."""
import sys; sys.path.insert(0, '.')
import logging
logging.basicConfig(level=logging.DEBUG)

from core_engine.simulation import simulate, TradePlan, FillModel, TradeLifecycle, TradeOutcome

# Simple BUY with TP at 103
prices = [101, 102, 103, 104, 105]
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

plan = TradePlan(
    side="BUY", entry=101, stop_loss=99.5,
    take_profits=[103], risk_percent=0.5, partials=[1.0],
)

fill = FillModel()
lc = TradeLifecycle(plan, fill)

# Start
res = lc.start(candles, 0)
print(f"Start: state={lc.state}, events={len(lc.events)}")
print(f"  Event: [{res.events[0].state}] @ {res.events[0].price}")

# Step through candles
for i in range(1, len(candles)):
    res = lc.step(candles, i)
    print(f"Step {i}: state={lc.state}, new_events={len(res.events)}, done={res.done}")
    for ev in res.events:
        print(f"  Event: [{ev.state}] @ {ev.price}: {ev.description}")

print(f"\nFinal state: {lc.state}")
print(f"Total events: {len(lc.events)}")
for ev in lc.events:
    print(f"  [{ev.state}] @ {ev.price}: {ev.description}")
