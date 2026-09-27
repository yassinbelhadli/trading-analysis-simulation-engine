"""security package — authentication, authorisation, audit."""
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / "config" / ".env"
load_dotenv(_env_path)
