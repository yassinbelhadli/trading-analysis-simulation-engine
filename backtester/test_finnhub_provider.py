import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.finnhub_provider import FinnhubProvider
from config.settings import FINNHUB_API_KEY

provider = FinnhubProvider(FINNHUB_API_KEY)

events = provider.fetch_events()

print("Events:", len(events))

for e in events[:10]:
    print(e)