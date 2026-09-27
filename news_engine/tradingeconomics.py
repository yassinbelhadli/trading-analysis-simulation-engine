import requests
import pandas as pd

from news_engine.news_provider import NewsProvider


class TradingEconomicsProvider(NewsProvider):

    BASE_URL = "https://api.tradingeconomics.com/calendar"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_events(self):

        params = {
            "c": self.api_key,
            "f": "json",
        }

        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        events = []

        for item in data:

            events.append({

                "time": pd.to_datetime(
                    item.get("Date")
                ),

                "currency": item.get("Currency"),

                "event": item.get("Event"),

                "impact": item.get("Importance"),

                "actual": item.get("Actual"),

                "forecast": item.get("Forecast"),

                "previous": item.get("Previous"),

            })

        return events