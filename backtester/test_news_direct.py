import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from news_engine.calendar import EconomicCalendar
from news_engine.news_filter import NewsFilter

calendar = EconomicCalendar()
calendar.load_from_csv(ROOT / "data" / "raw" / "news_events.csv")

print("NEWS LOADED:", len(calendar.get_events()))
print(calendar.to_dataframe().tail(10))

news_filter = NewsFilter(
    block_before_minutes=60,
    block_after_minutes=30,
    block_high_only=True,
)

result = news_filter.evaluate(
    symbol="XAUUSD",
    current_time="2025-01-20 13:15",
    calendar=calendar,
)

print(result.to_dict())