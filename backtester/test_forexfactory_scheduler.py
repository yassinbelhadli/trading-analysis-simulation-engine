# backtester/test_forexfactory_scheduler.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.providers.forexfactory_provider import ForexFactoryProvider
from news_engine.scheduler import NewsScheduler

provider = ForexFactoryProvider()
scheduler = NewsScheduler(provider)

count = scheduler.update()

print("Downloaded:", count)
print("Cached events:", len(scheduler.load()))

for e in scheduler.load()[:10]:
    print(e)