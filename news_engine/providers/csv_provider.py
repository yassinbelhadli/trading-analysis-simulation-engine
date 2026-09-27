from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from news_engine.news_provider import NewsProvider


class CSVNewsProvider(NewsProvider):
    """
    Reads economic news from a CSV file.

    Required columns:

    time
    currency
    event
    impact

    Optional:

    actual
    forecast
    previous
    """

    REQUIRED_COLUMNS = [
        "time",
        "currency",
        "event",
        "impact",
    ]

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)

    def fetch_events(self) -> List[Dict[str, Any]]:

        if not self.csv_path.exists():
            return []

        df = pd.read_csv(self.csv_path)

        for col in self.REQUIRED_COLUMNS:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        if "actual" not in df.columns:
            df["actual"] = None

        if "forecast" not in df.columns:
            df["forecast"] = None

        if "previous" not in df.columns:
            df["previous"] = None

        df["time"] = pd.to_datetime(df["time"])

        events = []

        for _, row in df.iterrows():

            events.append(
                {
                    "time": row["time"],
                    "currency": str(row["currency"]).upper(),
                    "event": row["event"],
                    "impact": str(row["impact"]).upper(),
                    "actual": row["actual"],
                    "forecast": row["forecast"],
                    "previous": row["previous"],
                }
            )

        return events