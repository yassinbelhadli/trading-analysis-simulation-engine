import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / "config" / ".env"

load_dotenv(ENV_PATH)

NEWS_PROVIDER = os.getenv("NEWS_PROVIDER", "CSV")
NEWS_REFRESH_MINUTES = int(os.getenv("NEWS_REFRESH_MINUTES", "60"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "ict_funded_pro_ea_bot")
BOT_USERNAME = TELEGRAM_BOT_USERNAME  # canonical name for integrations
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Telegram OIDC (Authorization Code + PKCE)
TELEGRAM_CLIENT_ID = os.getenv("TELEGRAM_CLIENT_ID", "")
TELEGRAM_CLIENT_SECRET = os.getenv("TELEGRAM_CLIENT_SECRET", "")
TELEGRAM_REDIRECT_URI = os.getenv("TELEGRAM_REDIRECT_URI", "")

ALLOW_REAL_TRADING = os.getenv("ALLOW_REAL_TRADING", "false").lower() == "true"
DEMO_ONLY = os.getenv("DEMO_ONLY", "true").lower() == "true"
USE_MOCK_TELEGRAM_SCAN = os.getenv("USE_MOCK_TELEGRAM_SCAN", "false").lower() == "true"

# --- Email (SMTP) ---
SMTP_HOST = os.getenv("SMTP_HOST") or "mail.privateemail.com"
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME") or os.getenv("SMTP_USER", "")
SMTP_USER = SMTP_USERNAME  # compatibility alias for existing deployments
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_SECURITY = os.getenv("SMTP_SECURITY", "starttls").lower()
SMTP_TIMEOUT_SECONDS = int(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))
SMTP_FROM = os.getenv("SMTP_FROM", "admin@ictfundedeapro.com")
SMTP_REPLY_TO = os.getenv("SMTP_REPLY_TO", "")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@ictfundedeapro.com")
BILLING_EMAIL = os.getenv("BILLING_EMAIL", "billing@ictfundedeapro.com")
CLIENT_PORTAL_URL = os.getenv("CLIENT_PORTAL_URL") or os.getenv("FRONTEND_URL", "http://localhost:3000")
FRONTEND_URL = CLIENT_PORTAL_URL  # compatibility alias for existing email links

# --- Authentication ---
JWT_SECRET = os.getenv("JWT_SECRET", ENCRYPTION_KEY)
JWT_ACCESS_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "30"))
JWT_REFRESH_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "30"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@ictfunded.com")
