from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pandas as pd


class SessionType(str, Enum):
    SYDNEY = "SYDNEY"
    TOKYO = "TOKYO"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    ASIAN_KILL_ZONE = "ASIAN_KILL_ZONE"
    LONDON_KILL_ZONE = "LONDON_KILL_ZONE"
    NEW_YORK_KILL_ZONE = "NEW_YORK_KILL_ZONE"
    LONDON_CLOSE = "LONDON_CLOSE"
    NEW_YORK_CLOSE = "NEW_YORK_CLOSE"


@dataclass
class ICTSession:
    session_type: SessionType
    label: str
    open_hour_utc: int
    close_hour_utc: int
    open_minute: int = 0
    close_minute: int = 0

    @property
    def duration_hours(self) -> float:
        diff = self.close_hour_utc - self.open_hour_utc
        if diff < 0:
            diff += 24
        return diff + (self.close_minute - self.open_minute) / 60.0

    def contains(self, dt: datetime) -> bool:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        utc_hour = dt.hour
        utc_min = dt.minute
        open_mins = self.open_hour_utc * 60 + self.open_minute
        close_mins = self.close_hour_utc * 60 + self.close_minute
        current_mins = utc_hour * 60 + utc_min
        if close_mins <= open_mins:
            return current_mins >= open_mins or current_mins <= close_mins
        return open_mins <= current_mins <= close_mins


ICT_SESSION_DEFS: List[ICTSession] = [
    ICTSession(SessionType.SYDNEY, "Sydney", 22, 6, 0, 0),
    ICTSession(SessionType.TOKYO, "Tokyo", 0, 8, 0, 0),
    ICTSession(SessionType.LONDON, "London", 7, 16, 0, 0),
    ICTSession(SessionType.NEW_YORK, "New York", 12, 21, 0, 0),
    ICTSession(SessionType.ASIAN_KILL_ZONE, "Asian Kill Zone", 0, 4, 0, 0),
    ICTSession(SessionType.LONDON_KILL_ZONE, "London Kill Zone", 7, 10, 0, 0),
    ICTSession(SessionType.NEW_YORK_KILL_ZONE, "New York Kill Zone", 12, 15, 0, 0),
    ICTSession(SessionType.LONDON_CLOSE, "London Close", 15, 17, 0, 0),
    ICTSession(SessionType.NEW_YORK_CLOSE, "New York Close", 21, 23, 0, 0),
]


@dataclass
class SessionAnalysis:
    timestamp: datetime
    current_session: Optional[ICTSession] = None
    sessions_active: List[str] = field(default_factory=list)
    is_kill_zone: bool = False
    kill_zones_active: List[str] = field(default_factory=list)
    asian_high: Optional[float] = None
    asian_low: Optional[float] = None
    asian_range: Optional[float] = None
    pdh: Optional[float] = None
    pdl: Optional[float] = None
    pdr: Optional[float] = None
    pdh_pdl_levels: Dict[str, float] = field(default_factory=dict)
    weekly_high: Optional[float] = None
    weekly_low: Optional[float] = None
    monthly_high: Optional[float] = None
    monthly_low: Optional[float] = None


KILL_ZONE_SESSIONS = {
    SessionType.ASIAN_KILL_ZONE, SessionType.LONDON_KILL_ZONE,
    SessionType.NEW_YORK_KILL_ZONE,
}


class SessionManager:
    def __init__(self):
        self.session_defs = ICT_SESSION_DEFS

    def get_active_sessions(self, dt: Optional[datetime] = None) -> List[ICTSession]:
        if dt is None:
            dt = datetime.now(timezone.utc)
        return [s for s in self.session_defs if s.contains(dt)]

    def get_kill_zones(self, dt: Optional[datetime] = None) -> List[ICTSession]:
        sessions = self.get_active_sessions(dt)
        return [s for s in sessions if s.session_type in KILL_ZONE_SESSIONS]

    def is_kill_zone(self, dt: Optional[datetime] = None) -> bool:
        return len(self.get_kill_zones(dt)) > 0

    def get_session_by_type(self, session_type: SessionType) -> Optional[ICTSession]:
        for s in self.session_defs:
            if s.session_type == session_type:
                return s
        return None

    def get_current_session(self, dt: Optional[datetime] = None) -> Optional[ICTSession]:
        if dt is None:
            dt = datetime.now(timezone.utc)
        for s in self.session_defs:
            if s.session_type in KILL_ZONE_SESSIONS:
                continue
            if s.contains(dt):
                return s
        return None

    def _get_session_high_low(self, df: pd.DataFrame, session: ICTSession) -> Tuple[float, float]:
        session_df = df[df.index.map(session.contains)]
        if session_df.empty:
            return 0.0, 0.0
        return float(session_df["high"].max()), float(session_df["low"].min())

    def get_asian_high_low(self, df: pd.DataFrame) -> Tuple[float, float]:
        asian = self.get_session_by_type(SessionType.TOKYO)
        if asian is None:
            return 0.0, 0.0
        return self._get_session_high_low(df, asian)

    def get_previous_day_high_low(self, df: pd.DataFrame) -> Tuple[float, float]:
        if df.empty:
            return 0.0, 0.0
        dates = sorted(set(d.date() for d in df.index))
        if len(dates) < 2:
            return 0.0, 0.0
        prev_date = dates[-2]
        prev = df[df.index.date == prev_date]
        if prev.empty:
            return 0.0, 0.0
        return float(prev["high"].max()), float(prev["low"].min())

    def get_weekly_high_low(self, df: pd.DataFrame) -> Tuple[float, float]:
        if df.empty:
            return 0.0, 0.0
        return float(df["high"].max()), float(df["low"].min())

    def get_monthly_high_low(self, df: pd.DataFrame) -> Tuple[float, float]:
        if df.empty:
            return 0.0, 0.0
        return float(df["high"].max()), float(df["low"].min())

    def analyze(self, df: pd.DataFrame, dt: Optional[datetime] = None) -> SessionAnalysis:
        if dt is None:
            dt = datetime.now(timezone.utc)
        active = self.get_active_sessions(dt)
        kill = self.get_kill_zones(dt)
        current = self.get_current_session(dt)
        asian_high, asian_low = self.get_asian_high_low(df)
        pdh, pdl = self.get_previous_day_high_low(df)
        wh, wl = self.get_weekly_high_low(df)
        mh, ml = self.get_monthly_high_low(df)
        return SessionAnalysis(
            timestamp=dt,
            current_session=current,
            sessions_active=[s.label for s in active],
            is_kill_zone=len(kill) > 0,
            kill_zones_active=[s.label for s in kill],
            asian_high=asian_high or None,
            asian_low=asian_low or None,
            asian_range=round(asian_high - asian_low, 5) if asian_high and asian_low else None,
            pdh=pdh or None,
            pdl=pdl or None,
            pdr=round(pdh - pdl, 5) if pdh and pdl else None,
            pdh_pdl_levels={"pdh": pdh, "pdl": pdl} if pdh and pdl else {},
            weekly_high=wh or None,
            weekly_low=wl or None,
            monthly_high=mh or None,
            monthly_low=ml or None,
        )


session_manager = SessionManager()
