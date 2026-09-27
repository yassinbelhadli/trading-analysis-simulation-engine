import sys
from pathlib import Path
from news_engine.news_service import NewsService

service = NewsService(interval_seconds=1800)
service.start()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.news_service import NewsService

service = NewsService(interval_seconds=1800)

service.start()