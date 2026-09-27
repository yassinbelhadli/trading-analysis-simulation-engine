from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd

from news_engine.repositories.base_repository import BaseNewsRepository


class CSVNewsRepository(BaseNewsRepository):
    COLUMNS = [
        "news_id",
        "time",
        "currency",
        "event",
        "impact",
        "actual",
        "forecast",
        "previous",
        "status",
        "version",
        "first_seen",
        "last_checked",
        "updated_at",
        "processed",
        "analyzed",
        "telegram_sent",
        "entry_processed",
    ]

    def __init__(self, path: str | Path = "data/processed/news_cache.csv"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def load_events(self) -> List[Dict]:
        df = self._read()
        return df.to_dict("records")

    def save_events(self, events: List[Dict]) -> None:
        normalized = [self._normalize_event(event) for event in events]

        df = pd.DataFrame(normalized)

        for col in self.COLUMNS:
            if col not in df.columns:
                df[col] = None

        df = df[self.COLUMNS]
        df = df.drop_duplicates(subset=["news_id"], keep="last")
        df.to_csv(self.path, index=False)

    def add_event(self, event: Dict) -> None:
        df = self._read()
        event = self._normalize_event(event)

        existing_ids = df["news_id"].astype(str).values

        if str(event["news_id"]) in existing_ids:
            self.update_event(event["news_id"], event)
            return

        df = pd.concat([df, pd.DataFrame([event])], ignore_index=True)
        df.to_csv(self.path, index=False)

    def update_event(self, news_id: str, updates: Dict) -> None:
        df = self._read()

        if df.empty or str(news_id) not in df["news_id"].astype(str).values:
            return

        idx = df.index[df["news_id"].astype(str) == str(news_id)][0]

        old_actual = df.at[idx, "actual"]
        old_forecast = df.at[idx, "forecast"]
        old_previous = df.at[idx, "previous"]

        for key, value in updates.items():
            if key in self.COLUMNS:
                df.at[idx, key] = value

        df.at[idx, "last_checked"] = self._now()

        changed = (
            self._normalize_value(old_actual) != self._normalize_value(df.at[idx, "actual"])
            or self._normalize_value(old_forecast) != self._normalize_value(df.at[idx, "forecast"])
            or self._normalize_value(old_previous) != self._normalize_value(df.at[idx, "previous"])
        )

        if changed:
            df.at[idx, "updated_at"] = self._now()
            df.at[idx, "version"] = self._safe_int(df.at[idx, "version"], 1) + 1
            df.at[idx, "processed"] = False
            df.at[idx, "analyzed"] = False
            df.at[idx, "telegram_sent"] = False
            df.at[idx, "entry_processed"] = False

            if not self._is_empty(df.at[idx, "actual"]):
                df.at[idx, "status"] = "RELEASED"
            else:
                df.at[idx, "status"] = "UPCOMING"

        df.to_csv(self.path, index=False)

    def get_event(self, news_id: str) -> Optional[Dict]:
        df = self._read()
        match = df[df["news_id"].astype(str) == str(news_id)]

        if match.empty:
            return None

        return match.iloc[0].to_dict()

    def event_exists(self, news_id: str) -> bool:
        return self.get_event(news_id) is not None

    def get_pending_events(self) -> List[Dict]:
        df = self._read()

        pending = df[
            (df["processed"].astype(str).str.lower() != "true")
            | (df["analyzed"].astype(str).str.lower() != "true")
        ]

        return pending.to_dict("records")

    def mark_processed(self, news_id: str) -> None:
        self.update_event(news_id, {"processed": True})

    def mark_analyzed(self, news_id: str) -> None:
        self.update_event(news_id, {"analyzed": True})

    def mark_telegram_sent(self, news_id: str) -> None:
        self.update_event(news_id, {"telegram_sent": True})

    def mark_entry_processed(self, news_id: str) -> None:
        self.update_event(news_id, {"entry_processed": True})

    def _ensure_file(self) -> None:
        if not self.path.exists():
            pd.DataFrame(columns=self.COLUMNS).to_csv(self.path, index=False)

    def _read(self) -> pd.DataFrame:
        self._ensure_file()
        df = pd.read_csv(self.path)

        for col in self.COLUMNS:
            if col not in df.columns:
                df[col] = None

        return df[self.COLUMNS]

    def _normalize_event(self, event: Dict) -> Dict:
        now = self._now()
        event = dict(event)

        if self._is_empty(event.get("news_id")):
            event["news_id"] = self._make_news_id(event)

        if self._is_empty(event.get("status")):
            event["status"] = "RELEASED" if not self._is_empty(event.get("actual")) else "UPCOMING"

        if self._is_empty(event.get("version")):
            event["version"] = 1

        if self._is_empty(event.get("first_seen")):
            event["first_seen"] = now

        event["last_checked"] = now

        if self._is_empty(event.get("updated_at")):
            event["updated_at"] = None

        for flag in ["processed", "analyzed", "telegram_sent", "entry_processed"]:
            if self._is_empty(event.get(flag)):
                event[flag] = False

        for col in self.COLUMNS:
            event.setdefault(col, None)

        return event

    def _make_news_id(self, event: Dict) -> str:
        time = pd.to_datetime(event.get("time"), errors="coerce")
        time_str = time.strftime("%Y%m%d_%H%M%S") if not pd.isna(time) else "UNKNOWN_TIME"

        currency = str(event.get("currency", "UNK")).upper().strip()
        name = str(event.get("event", "UNKNOWN")).upper().strip()
        name = "".join(c if c.isalnum() else "_" for c in name)
        name = "_".join(part for part in name.split("_") if part)[:40]

        return f"{currency}_{name}_{time_str}"

    def _now(self) -> str:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    def _is_empty(self, value) -> bool:
        try:
            if value is None:
                return True
            if pd.isna(value):
                return True

            value = str(value).strip().lower()
            return value in ["", "nan", "none", "nat"]
        except Exception:
            return True

    def _normalize_value(self, value):
        if self._is_empty(value):
            return None
        return str(value).strip()

    def _safe_int(self, value, default=1) -> int:
        try:
            if self._is_empty(value):
                return default
            return int(float(value))
        except Exception:
            return default