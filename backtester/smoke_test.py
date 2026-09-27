"""
Smoke test: inject synthetic event into validation harness.
Run while demo_validation.py is already running.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("smoke_test")

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType

async def smoke_test():
    print("=" * 60)
    print("SMOKE TEST: Injecting synthetic events")
    print("=" * 60)

    events = [
        ("SETUP_DETECTED", {
            "candidate_id": "smoke-test-001",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "score": 85.5,
            "confidence": 0.88,
            "reasons": ["FVG", "OrderBlock"],
        }),
        ("PAPER_TRADE_PLANNED", {
            "candidate_id": "smoke-test-001",
            "id": "paper_trade_abc123",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "entry": 2350.0,
            "stop_loss": 2340.0,
            "take_profit": 2380.0,
            "lot_size": 0.05,
            "risk_reward": 3.0,
        }),
        ("TRADE_OPENED", {
            "candidate_id": "smoke-test-001",
            "ticket": 12345678,
            "symbol": "XAUUSD",
            "direction": "BUY",
            "entry": 2350.0,
            "sl": 2340.0,
            "tp": 2380.0,
            "lot_size": 0.05,
        }),
        ("BREAK_EVEN_MOVED", {
            "ticket": 12345678,
            "new_sl": 2350.0,
        }),
        ("PARTIAL_CLOSE", {
            "ticket": 12345678,
            "close_volume": 0.025,
        }),
        ("TRADE_CLOSED", {
            "ticket": 12345678,
            "profit": 125.0,
        }),
    ]

    for event_type, data in events:
        print(f"Publishing {event_type} -> {data.get('candidate_id') or data.get('ticket', '')}")
        await event_bus.publish(event_type, {
            "account_id": "smoke-test",
            "user_id": "smoke-test",
            "event_type": event_type,
            "trade_id": str(data.get("ticket", "")),
            "message": f"SMOKE: {event_type}",
            "data": data,
            "timestamp": None,
        })
        await asyncio.sleep(0.3)

    print("\nDone publishing. Check:")
    print("  1. data/validation/replay/events_*.jsonl - should have 6 new lines")
    print("  2. data/validation/metrics_*.json - counters should be > 0")

if __name__ == "__main__":
    asyncio.run(smoke_test())
