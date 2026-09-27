from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import pandas as pd


@dataclass
class EconomicEvent:
    time: datetime
    currency: str
    event_name: str
    impact: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EconomicCalendar:
    def __init__(self):
        self.events: List[EconomicEvent] = []

    def clear(self):
        self.events = []

    def add_event(
        self,
        event_time,
        currency: str,
        event_name: str,
        impact: str,
    ):
        if isinstance(event_time, str):
            event_time = pd.to_datetime(event_time)

        self.events.append(
            EconomicEvent(
                time=event_time,
                currency=str(currency).upper().strip(),
                event_name=str(event_name).strip(),
                impact=str(impact).upper().strip(),
            )
        )

        self.events.sort(key=lambda e: pd.to_datetime(e.time))

    def load_from_dataframe(
        self,
        df: pd.DataFrame,
        time_col="time",
        currency_col="currency",
        event_col="event",
        impact_col="impact",
        clear_existing: bool = False,
    ):
        if clear_existing:
            self.clear()

        required = [time_col, currency_col, event_col, impact_col]
        missing = [c for c in required if c not in df.columns]

        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        for _, row in df.iterrows():
            self.add_event(
                event_time=row[time_col],
                currency=row[currency_col],
                event_name=row[event_col],
                impact=row[impact_col],
            )

    def load_from_csv(
        self,
        path,
        time_col="time",
        currency_col="currency",
        event_col="event",
        impact_col="impact",
        clear_existing: bool = False,
    ):
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"News CSV not found: {path}")

        df = pd.read_csv(path)

        self.load_from_dataframe(
            df=df,
            time_col=time_col,
            currency_col=currency_col,
            event_col=event_col,
            impact_col=impact_col,
            clear_existing=clear_existing,
        )

    def get_events(self) -> List[EconomicEvent]:
        return self.events

    def get_events_for_day(self, day) -> List[EconomicEvent]:
        day = pd.to_datetime(day).date()

        return [
            e
            for e in self.events
            if pd.to_datetime(e.time).date() == day
        ]

    def get_events_between(
        self,
        start_time,
        end_time,
    ) -> List[EconomicEvent]:
        start_time = pd.to_datetime(start_time)
        end_time = pd.to_datetime(end_time)

        return [
            e
            for e in self.events
            if start_time <= pd.to_datetime(e.time) <= end_time
        ]

    def to_dataframe(self) -> pd.DataFrame:
        if not self.events:
            return pd.DataFrame(
                columns=[
                    "time",
                    "currency",
                    "event_name",
                    "impact",
                ]
            )

        return pd.DataFrame(
            [
                {
                    "time": e.time,
                    "currency": e.currency,
                    "event_name": e.event_name,
                    "impact": e.impact,
                }
                for e in self.events
            ]
        )