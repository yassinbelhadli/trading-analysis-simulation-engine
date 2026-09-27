import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType


received = []


def listener(event):
    print(f"EVENT RECEIVED -> {event['event_type']}")
    received.append(event)


# Subscribe
event_bus.subscribe(EventType.TP_HIT.value, listener)


# Publish test event
event_bus.publish(
    EventType.TP_HIT.value,
    {
        "event_type": EventType.TP_HIT.value,
        "trade_id": "TEST_001",
        "message": "TP Hit",
        "data": {
            "symbol": "XAUUSD",
            "profit": 250,
        },
    },
)

assert len(received) == 1
assert received[0]["trade_id"] == "TEST_001"

print("=" * 60)
print("EVENT BUS TEST PASSED")
print("=" * 60)