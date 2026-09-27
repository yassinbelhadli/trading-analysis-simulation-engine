import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import FMP_API_KEY
from news_engine.fmp_provider import FMPNewsProvider

provider = FMPNewsProvider(
    api_key=FMP_API_KEY,
)

events = provider.fetch_events()

print("Events:", len(events))

for e in events[:10]:
    print(e)