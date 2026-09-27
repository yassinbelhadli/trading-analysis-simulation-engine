import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from monitoring.logs.notifications import notifications

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType


event_bus.publish(

    EventType.TP_HIT.value,

    {

        "event_type": EventType.TP_HIT.value,

        "trade_id": "TRADE_TEST",

        "message": "Take Profit Hit",

        "data": {
            "symbol": "XAUUSD",
            "profit": 250,
        },

    },

)

print()

print("History =", len(notifications.get_history()))