import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.parsers.csv_parser import CSVParser

parser = CSVParser()

events = parser.read("data/processed/news_cache.csv")

print(f"Rows : {len(events)}")

if events:
    print(events[0])