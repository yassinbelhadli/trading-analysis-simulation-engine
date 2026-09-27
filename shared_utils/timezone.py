"""
Centralized IANA timezone definitions and validation for the application.

All timezone selection UIs and validation logic should import from this module
to guarantee a single source of truth.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Region-organized IANA timezone list
# ---------------------------------------------------------------------------

TIMEZONE_REGIONS: list[dict] = [
    {
        "region": "Africa",
        "timezones": [
            {"label": "Morocco — Casablanca", "iana": "Africa/Casablanca"},
            {"label": "Algeria — Algiers", "iana": "Africa/Algiers"},
            {"label": "Tunisia — Tunis", "iana": "Africa/Tunis"},
            {"label": "Egypt — Cairo", "iana": "Africa/Cairo"},
            {"label": "South Africa — Johannesburg", "iana": "Africa/Johannesburg"},
            {"label": "Nigeria — Lagos", "iana": "Africa/Lagos"},
            {"label": "Kenya — Nairobi", "iana": "Africa/Nairobi"},
        ],
    },
    {
        "region": "Europe",
        "timezones": [
            {"label": "France — Paris", "iana": "Europe/Paris"},
            {"label": "UK — London", "iana": "Europe/London"},
            {"label": "Germany — Berlin", "iana": "Europe/Berlin"},
            {"label": "Spain — Madrid", "iana": "Europe/Madrid"},
            {"label": "Italy — Rome", "iana": "Europe/Rome"},
            {"label": "Netherlands — Amsterdam", "iana": "Europe/Amsterdam"},
            {"label": "Portugal — Lisbon", "iana": "Europe/Lisbon"},
        ],
    },
    {
        "region": "North America",
        "timezones": [
            {"label": "United States — New York", "iana": "America/New_York"},
            {"label": "United States — Los Angeles", "iana": "America/Los_Angeles"},
            {"label": "United States — Chicago", "iana": "America/Chicago"},
            {"label": "United States — Denver", "iana": "America/Denver"},
            {"label": "Canada — Toronto", "iana": "America/Toronto"},
            {"label": "Canada — Vancouver", "iana": "America/Vancouver"},
            {"label": "Mexico — Mexico City", "iana": "America/Mexico_City"},
        ],
    },
    {
        "region": "South America",
        "timezones": [
            {"label": "Brazil — São Paulo", "iana": "America/Sao_Paulo"},
            {"label": "Argentina — Buenos Aires", "iana": "America/Argentina/Buenos_Aires"},
            {"label": "Colombia — Bogota", "iana": "America/Bogota"},
        ],
    },
    {
        "region": "Asia",
        "timezones": [
            {"label": "UAE — Dubai", "iana": "Asia/Dubai"},
            {"label": "Saudi Arabia — Riyadh", "iana": "Asia/Riyadh"},
            {"label": "Turkey — Istanbul", "iana": "Europe/Istanbul"},
            {"label": "India — Mumbai", "iana": "Asia/Kolkata"},
            {"label": "Pakistan — Karachi", "iana": "Asia/Karachi"},
            {"label": "Japan — Tokyo", "iana": "Asia/Tokyo"},
            {"label": "China — Shanghai", "iana": "Asia/Shanghai"},
            {"label": "South Korea — Seoul", "iana": "Asia/Seoul"},
            {"label": "Singapore", "iana": "Asia/Singapore"},
            {"label": "Hong Kong", "iana": "Asia/Hong_Kong"},
            {"label": "Thailand — Bangkok", "iana": "Asia/Bangkok"},
            {"label": "Indonesia — Jakarta", "iana": "Asia/Jakarta"},
        ],
    },
    {
        "region": "Oceania",
        "timezones": [
            {"label": "Australia — Sydney", "iana": "Australia/Sydney"},
            {"label": "Australia — Melbourne", "iana": "Australia/Melbourne"},
            {"label": "New Zealand — Auckland", "iana": "Pacific/Auckland"},
        ],
    },
]

# ---------------------------------------------------------------------------
# Build the valid-set once at import time
# ---------------------------------------------------------------------------

VALID_IANA_TIMEZONES: set[str] = {
    tz["iana"] for region in TIMEZONE_REGIONS for tz in region["timezones"]
}

# ---------------------------------------------------------------------------
# Default timezone for new users
# ---------------------------------------------------------------------------

DEFAULT_TIMEZONE: str = "Africa/Casablanca"

# ---------------------------------------------------------------------------
# Lookup helper: label → iana mapping for quick reverse lookups
# ---------------------------------------------------------------------------

_IANA_TO_LABEL: dict[str, str] = {
    tz["iana"]: tz["label"]
    for region in TIMEZONE_REGIONS
    for tz in region["timezones"]
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def is_valid_timezone(tz: str) -> bool:
    """Return True if *tz* is a recognized IANA timezone in our allow-list."""
    return tz in VALID_IANA_TIMEZONES


def get_timezone_label(tz: str) -> str:
    """Return human-readable label for an IANA timezone, or the IANA ID if not found."""
    return _IANA_TO_LABEL.get(tz, tz)
