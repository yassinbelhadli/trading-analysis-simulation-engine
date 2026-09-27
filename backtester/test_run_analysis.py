import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.live_news_updater import LiveNewsUpdater

updater = LiveNewsUpdater()

# تنظيف الـ Cache
updater.cache.clear()

# خبر تجريبي
fake_event = {
    "news_id": "TEST_CORE_PCE",
    "time": "2026-06-26 13:30:00",
    "currency": "USD",
    "event": "Core PCE Price Index m/m",
    "impact": "HIGH",
    "actual": 0.6,
    "forecast": 0.3,
    "previous": 0.2,
}

updater.cache.add_event(fake_event)

print("Fake event inserted.\n")

updater.run_analysis()