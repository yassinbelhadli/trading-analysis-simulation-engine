import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

import pandas as pd

from news_engine.calendar import EconomicCalendar
from news_engine.news_filter import NewsFilter


print("=" * 70)
print("NEWS FILTER TEST")
print("=" * 70)

calendar = EconomicCalendar()

calendar.load_from_csv(
    "data/raw/news_events.csv"
)

news_filter = NewsFilter(
    block_before_minutes=60,
    block_after_minutes=30,
    block_high_only=True,
)

symbols = [
    "XAUUSD",
    "USTEC",
    "BTCUSDm",
]

for symbol in symbols:

    print(f"\n===== {symbol} =====")

    blocked = 0
    allowed = 0

    for event in calendar.get_events():

        current_time = (
            pd.to_datetime(event.time)
            - pd.Timedelta(minutes=30)
        )

        result = news_filter.evaluate(
            symbol=symbol,
            current_time=current_time,
            calendar=calendar,
        )

        if result.allowed:
            allowed += 1
        else:
            blocked += 1

            print(
                f"BLOCKED | "
                f"{result.blocking_event} | "
                f"{result.blocking_currency} | "
                f"{result.minutes_to_event} min"
            )

    print(f"\nAllowed : {allowed}")
    print(f"Blocked : {blocked}")

print("\n" + "=" * 70)