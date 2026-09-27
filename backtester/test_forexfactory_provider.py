import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.providers.forexfactory_provider import ForexFactoryProvider

provider = ForexFactoryProvider()

events = provider.fetch_events()

print("Events:", len(events))

for e in events[:20]:
    print(e)