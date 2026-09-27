from news_engine.providers.csv_provider import CSVNewsProvider
from news_engine.scheduler import NewsScheduler

provider = CSVNewsProvider("data/raw/news_events.csv")

scheduler = NewsScheduler(provider)

count = scheduler.update()

print("Downloaded:", count)

print("Cache:")

for event in scheduler.load():
    print(event)