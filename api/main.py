from __future__ import annotations

import asyncio
import datetime
import logging
import os
import secrets
from pathlib import Path

# Load config/.env manually without requiring python-dotenv
_env_path = Path(__file__).resolve().parent.parent / "config" / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _val = _line.split("=", 1)
            _key, _val = _key.strip(), _val.strip().strip("\"'")
            if _key and not os.environ.get(_key):
                os.environ[_key] = _val

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.routes.admin.bundle import admin_router as admin_bundle_router
from api.routes.admin_health import admin_health_router
from api.routes.admin_users import admin_users_router
from api.routes.admin_accounts import admin_accounts_router
from api.routes.admin_licenses import admin_licenses_router
from api.routes.admin_audit import admin_audit_router
from api.routes.admin_metrics import admin_metrics_router
from api.routes.auth_router import auth_router
from api.routes.client.accounts import router as client_accounts_router
from api.routes.client.dashboard import router as client_router
from api.routes.client.ea import router as client_ea_router
from api.routes.client.support import router as client_support_router
from api.routes.client.telegram import router as client_telegram_router
from api.routes.client.news import router as client_news_router
from api.routes.client.payments import router as client_payments_router
from api.routes.client.payment_configs import router as client_payment_configs_router
from api.routes.licenses import router as client_licenses_router
from api.routes.screenshots import router as screenshots_router
from database.db import init_db

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ICT Funded EA — API",
    version="1.0.0",
)

# CORS: explicit allowlist only. The API authenticates via Authorization
# headers (credentials=False), but a wildcard origin is still wrong for a
# trading platform: any website could be a vector for CSRF-style requests.
# Defaults cover local development; FRONTEND_URL (or PORTAL_URLS) extends it.
_default_origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",   # Client portal
    "http://localhost:3001", "http://127.0.0.1:3001",   # Admin portal
    "http://localhost:3002", "http://127.0.0.1:3002",   # Owner portal
    "http://localhost:3010", "http://127.0.0.1:3010",   # Public website
]
_extra_origins = [
    o.strip() for o in os.getenv("FRONTEND_URL", "").replace(",", " ").split()
    if o.strip()
]
_extra_origins += [
    o.strip() for o in os.getenv("PORTAL_URLS", "").replace(",", " ").split()
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Legacy admin token fallback (migration path)
# ---------------------------------------------------------------------------
# Fail closed: never expose legacy /admin routes without a valid token. If no
# token is configured, generate a random one so the endpoints stay locked.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
if not ADMIN_TOKEN:
    ADMIN_TOKEN = secrets.token_urlsafe(32)
    logger.warning(
        "ADMIN_TOKEN is not set — legacy /admin API is locked. "
        "Set ADMIN_TOKEN in config/.env to use the legacy endpoints."
    )


async def verify_admin_legacy(x_admin_token: str = Header(None)):
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid admin token")


# ---------------------------------------------------------------------------
# Auth routes (public — no auth required)
# ---------------------------------------------------------------------------
app.include_router(auth_router, prefix="", tags=["auth"])

# ---------------------------------------------------------------------------
# New Admin API  (JWT + permission-based)
# Each sub-route uses require_permission() internally.
# ---------------------------------------------------------------------------
app.include_router(admin_bundle_router, prefix="/api")

# ---------------------------------------------------------------------------
# Client API (JWT-based — for client dashboard)
# ---------------------------------------------------------------------------
app.include_router(client_router, prefix="/api")
app.include_router(client_accounts_router, prefix="/api")
app.include_router(client_telegram_router, prefix="/api")
app.include_router(client_news_router, prefix="/api")
app.include_router(client_ea_router, prefix="/api")
app.include_router(client_support_router, prefix="/api")
app.include_router(client_payments_router, prefix="/api")
app.include_router(client_payment_configs_router, prefix="/api")
app.include_router(client_licenses_router, prefix="/api")
app.include_router(screenshots_router, prefix="/api")

# ---------------------------------------------------------------------------
# Legacy admin routes  (static token — migration path, deprecated)
# ---------------------------------------------------------------------------
app.include_router(admin_health_router, prefix="/admin", tags=["admin", "health"],
                   dependencies=[Depends(verify_admin_legacy)])
app.include_router(admin_users_router, prefix="/admin", tags=["admin", "users"],
                   dependencies=[Depends(verify_admin_legacy)])
app.include_router(admin_accounts_router, prefix="/admin", tags=["admin", "accounts"],
                   dependencies=[Depends(verify_admin_legacy)])
app.include_router(admin_licenses_router, prefix="/admin", tags=["admin", "licenses"],
                   dependencies=[Depends(verify_admin_legacy)])
app.include_router(admin_audit_router, prefix="/admin", tags=["admin", "audit"],
                   dependencies=[Depends(verify_admin_legacy)])
app.include_router(admin_metrics_router, prefix="/admin", tags=["admin", "metrics"],
                   dependencies=[Depends(verify_admin_legacy)])

# ---------------------------------------------------------------------------
# Startup: background news engine (ForexFactory → CSV → Trading Engine)
# ---------------------------------------------------------------------------
import threading


def _start_news_service():
    import time
    try:
        from news_engine.news_service import NewsService
        interval_min = int(os.getenv("NEWS_REFRESH_MINUTES", "60"))
        # First fetch after 30 seconds (avoids immediate rate-limit)
        time.sleep(30)
        svc = NewsService(interval_seconds=interval_min * 60)
        logger.info("NewsService started (interval=%dmin)", interval_min)
        svc.start()
    except Exception as e:
        logger.warning("NewsService not available: %s", e)


@app.on_event("startup")
async def startup():
    # Ensure all DB tables exist
    try:
        await init_db()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning("init_db failed: %s", e)

    # Background news engine (ForexFactory → CSV)
    logger.info("Starting background news service...")
    thread = threading.Thread(target=_start_news_service, daemon=True)
    thread.start()

    # Background DB sync + Telegram alerts (every 10 min)
    async def _news_broadcast_loop():
        from api.services.news_broadcast import (
            sync_csv_to_db,
            check_and_alert_upcoming_events,
            send_weekly_calendar,
        )
        _last_sunday_ping = None
        while True:
            try:
                await sync_csv_to_db()
                await check_and_alert_upcoming_events()

                now = datetime.datetime.now(datetime.timezone.utc)
                if now.weekday() == 6:  # Sunday
                    last = _last_sunday_ping
                    if last is None or (now - last).total_seconds() > 86400:
                        await send_weekly_calendar()
                        _last_sunday_ping = now
            except Exception as e:
                logger.warning("news_broadcast_loop: %s", e)
            await asyncio.sleep(600)  # 10 minutes

    asyncio.create_task(_news_broadcast_loop())
    logger.info("News broadcast loop scheduled (interval=10min)")

    # ── Economic Calendar Scheduler (Phase 3) ────────────────────
    try:
        from economic_calendar.production_scheduler import production_calendar_scheduler
        await production_calendar_scheduler.start()
        logger.info("ProductionCalendarScheduler started")
    except Exception as e:
        logger.warning("ProductionCalendarScheduler not available: %s", e)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
