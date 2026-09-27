from typing import List, Dict, Optional

from sqlalchemy.orm import Session

from news_engine.repositories.base_repository import BaseNewsRepository
from database.models import NewsEvent


class PostgresNewsRepository(BaseNewsRepository):

    def __init__(self, session: Session):
        self.session = session

    def load_events(self) -> List[Dict]:
        events = self.session.query(NewsEvent).all()
        return [event.to_dict() for event in events]

    def save_events(self, events: List[Dict]) -> None:
        for event in events:
            self.add_event(event)

    def add_event(self, event: Dict) -> None:

        if self.event_exists(event["news_id"]):
            self.update_event(event["news_id"], event)
            return

        db_event = NewsEvent(**event)

        self.session.add(db_event)
        self.session.commit()

    def update_event(self, news_id: str, updates: Dict) -> None:

        event = (
            self.session.query(NewsEvent)
            .filter(NewsEvent.news_id == news_id)
            .first()
        )

        if event is None:
            return

        for key, value in updates.items():

            if hasattr(event, key):
                setattr(event, key, value)

        self.session.commit()

    def get_event(self, news_id: str) -> Optional[Dict]:

        event = (
            self.session.query(NewsEvent)
            .filter(NewsEvent.news_id == news_id)
            .first()
        )

        if event is None:
            return None

        return event.to_dict()

    def event_exists(self, news_id: str) -> bool:

        return (
            self.session.query(NewsEvent)
            .filter(NewsEvent.news_id == news_id)
            .first()
            is not None
        )

    def get_pending_events(self) -> List[Dict]:

        events = (
            self.session.query(NewsEvent)
            .filter(
                (NewsEvent.processed == False)
                | (NewsEvent.analyzed == False)
            )
            .all()
        )

        return [event.to_dict() for event in events]

    def mark_processed(self, news_id: str) -> None:
        self.update_event(news_id, {"processed": True})

    def mark_analyzed(self, news_id: str) -> None:
        self.update_event(news_id, {"analyzed": True})

    def mark_telegram_sent(self, news_id: str) -> None:
        self.update_event(news_id, {"telegram_sent": True})

    def mark_entry_processed(self, news_id: str) -> None:
        self.update_event(news_id, {"entry_processed": True})