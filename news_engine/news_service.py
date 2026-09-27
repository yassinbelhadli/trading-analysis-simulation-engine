import time
from datetime import datetime

from news_engine.live_news_updater import LiveNewsUpdater


class NewsService:

    def __init__(self, interval_seconds=60):
        self.interval = interval_seconds
        self.updater = LiveNewsUpdater()

    def run_once(self):

        print("=" * 60)
        print(f"[{datetime.now()}] NEWS SERVICE")
        print("=" * 60)

        try:
            self.updater.run()

        except Exception as e:
            print(f"[ERROR] {e}")

    def start(self):

        print()
        print("News Service Started")
        print(f"Interval : {self.interval} seconds")
        print()

        while True:

            self.run_once()

            time.sleep(self.interval)