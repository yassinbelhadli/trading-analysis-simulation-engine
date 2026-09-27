"""Seed the news cache with sample economic events for the current week."""
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
start = now - timedelta(days=now.weekday() + 1)
start = start.replace(hour=0, minute=0, second=0, microsecond=0)

events = []
template = [
    (0, "08:30", "USD", "Unemployment Rate", "HIGH"),
    (0, "10:00", "USD", "ISM Manufacturing PMI", "HIGH"),
    (1, "08:30", "USD", "CB Consumer Confidence", "HIGH"),
    (1, "14:00", "USD", "JOLTS Job Openings", "MEDIUM"),
    (2, "08:15", "USD", "ADP Non-Farm Employment Change", "HIGH"),
    (2, "10:00", "USD", "ISM Services PMI", "HIGH"),
    (2, "14:30", "USD", "Crude Oil Inventories", "MEDIUM"),
    (3, "08:30", "USD", "Initial Jobless Claims", "HIGH"),
    (3, "10:00", "USD", "Trade Balance", "MEDIUM"),
    (4, "08:30", "USD", "Non-Farm Payrolls", "HIGH"),
    (4, "08:30", "USD", "Average Hourly Earnings m/m", "HIGH"),
    (4, "10:00", "USD", "Michigan Consumer Sentiment", "HIGH"),
]

for days_offset, time_str, currency, event_name, impact in template:
    h, m = map(int, time_str.split(":"))
    event_time = start + timedelta(days=days_offset, hours=h, minutes=m)
    is_past = event_time < now

    name_clean = event_name.replace(" ", "_").replace("/", "_")
    events.append({
        "news_id": f"USD_{name_clean}_{event_time.strftime('%Y%m%d_%H%M%S')}",
        "time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
        "currency": currency,
        "event": event_name,
        "impact": impact,
        "actual": "0.3%" if is_past else None,
        "forecast": "0.3%",
        "previous": "0.2%",
        "status": "RELEASED" if is_past else "UPCOMING",
        "version": 1,
        "first_seen": event_time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_checked": now.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": "",
        "processed": "True" if is_past else "False",
        "analyzed": "True" if is_past else "False",
        "telegram_sent": "False",
        "entry_processed": "False",
    })

csv_path = Path(__file__).parent / "data" / "processed" / "news_cache.csv"
csv_path.parent.mkdir(parents=True, exist_ok=True)
df = pd.DataFrame(events)
df.to_csv(csv_path, index=False)
print(f"Seeded {len(events)} events from {start.date()} to {(start + timedelta(days=7)).date()}")
