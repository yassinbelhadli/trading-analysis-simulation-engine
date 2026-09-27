"""
api.auth — thin wrapper around security.auth.

Loads .env on import and re-exports all auth primitives.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[1] / "config" / ".env"
load_dotenv(_env_path)

from security.auth import *  # noqa: F401, F403
from security.auth import __all__ as _all  # noqa: F811

__all__ = _all
