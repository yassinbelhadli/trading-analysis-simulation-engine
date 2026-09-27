from news_engine.news_cache import NewsCache


class NewsScheduler:

    def __init__(self, provider):
        self.provider = provider
        self.cache = NewsCache()

    def update(self):

        events = self.provider.fetch_events()

        self.cache.save_events(events)

        return len(events)

    def load(self):

        return self.cache.load_events()