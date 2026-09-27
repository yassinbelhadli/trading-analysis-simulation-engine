import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.providers.csv_provider import CSVNewsProvider

provider = CSVNewsProvider("data/raw/news_events.csv")

events = provider.fetch_events()

print("Events:", len(events))

if events:
    print(events[0])