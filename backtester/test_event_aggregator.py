import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.fundamental_analyzer import FundamentalAnalyzer
from news_engine.event_aggregator import EventAggregator

analyzer = FundamentalAnalyzer()
aggregator = EventAggregator()

results = [
    analyzer.analyze_event("Core PCE Price Index m/m", "USD", "HIGH", 0.6, 0.3, 0.2),
    analyzer.analyze_event("Final GDP q/q", "USD", "HIGH", 2.1, 1.6, 1.6),
    analyzer.analyze_event("Unemployment Claims", "USD", "MEDIUM", 230, 225, 226),
]

final = aggregator.aggregate(results)

print(final.to_dict())