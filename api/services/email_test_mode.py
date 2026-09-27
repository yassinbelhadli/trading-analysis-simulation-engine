"""DEV-ONLY local email mailbox for registration / verification testing.

Purpose
-------
When SMTP is not configured (local development), the registration and
password-reset flows still create server-side verification tokens, but the
codes never reach the user because ``send_email`` returns False.  This module
implements the ``EMAIL_TEST_MODE`` mechanism documented in
``docs/human_validation_kit.md``: while enabled, verification / reset codes
are written to a clearly marked LOCAL-ONLY mailbox file instead of being sent
through SMTP, so a human or a QA script can read them and complete the flow.

Guards (security)
-----------------
1. Disabled by default — ``EMAIL_TEST_MODE`` must be explicitly "true".
2. Never active in a production environment (``APP_ENV``/``ENVIRONMENT`` in
   ``{production, prod}``) — falls back to normal SMTP behaviour.
3. Never active when real SMTP credentials are configured (``SMTP_USER`` and
   ``SMTP_PASS`` both present) — we never silently redirect real mail into a
   dev file.
4. The mailbox stores ONLY: recipient address, subject, kind, the single-use
   verification/reset code and its link, plus a timestamp.  It never stores
   passwords, SMTP credentials, or any secret besides the code itself, which
   is a short-lived single-use token by design.

This file is safe to import in production code paths: every function returns
False / [] unless ``EMAIL_TEST_MODE`` is enabled.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]  # project root
MAILBOX_DIR = BASE_DIR / "logs" / "dev_mailbox"
MAILBOX_FILE = MAILBOX_DIR / "mailbox.json"

_lock = threading.Lock()


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def is_email_test_mode_enabled() -> bool:
    """True only when EMAIL_TEST_MODE is explicitly on AND we are in a safe,
    local development context (no production env, no real SMTP credentials)."""
    if not _env_flag("EMAIL_TEST_MODE"):
        return False

    env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()
    if env in ("production", "prod"):
        logger.warning("EMAIL_TEST_MODE ignored: running in '%s' environment", env)
        return False

    if (os.getenv("SMTP_USERNAME") or os.getenv("SMTP_USER") or "").strip() and \
       (os.getenv("SMTP_PASS") or "").strip():
        logger.warning(
            "EMAIL_TEST_MODE ignored: real SMTP credentials are configured; "
            "mail will be sent normally, never written to the dev mailbox"
        )
        return False

    return True


def dev_mailbox_path() -> Path:
    """Absolute path of the local-only mailbox file (for docs / tooling)."""
    return MAILBOX_FILE


def write_dev_mailbox_message(
    to: str,
    subject: str,
    code: str,
    link: str = "",
    kind: str = "email",
) -> bool:
    """Append one clearly-marked dev-only delivery record. Returns True only
    when EMAIL_TEST_MODE is enabled and the record was written."""
    if not is_email_test_mode_enabled():
        return False

    record = {
        "mechanism": "EMAIL_TEST_MODE (dev-only local mailbox)",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "to": to,
        "subject": subject,
        "kind": kind,
        "code": code,
        "link": link,
    }

    with _lock:
        records: List[dict] = []
        if MAILBOX_FILE.exists():
            try:
                loaded = json.loads(MAILBOX_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    records = loaded
            except (ValueError, OSError):
                records = []
        # Monotonic sequence so "newest" is well-defined even when multiple
        # records are written within the same second.
        record["seq"] = (max((r.get("seq", 0) for r in records), default=0) + 1)
        records.append(record)
        try:
            MAILBOX_DIR.mkdir(parents=True, exist_ok=True)
            MAILBOX_FILE.write_text(
                json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:  # pragma: no cover - filesystem failure in dev
            logger.warning("EMAIL_TEST_MODE: could not write dev mailbox: %s", exc)
            return False

    logger.info(
        "EMAIL_TEST_MODE active: %s code for %s written to dev mailbox "
        "(logs/dev_mailbox/mailbox.json)",
        kind, to,
    )
    return True


def read_dev_mailbox(
    to: Optional[str] = None,
    kind: Optional[str] = None,
    last: Optional[int] = None,
) -> List[dict]:
    """Read dev-mailbox records (newest first). Returns [] unless
    EMAIL_TEST_MODE is enabled. Intended for local QA scripts and humans."""
    if not is_email_test_mode_enabled() or not MAILBOX_FILE.exists():
        return []

    try:
        records = json.loads(MAILBOX_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    if not isinstance(records, list):
        return []

    if to:
        records = [r for r in records if r.get("to", "").lower() == to.strip().lower()]
    if kind:
        records = [r for r in records if r.get("kind") == kind]

    records = sorted(records, key=lambda r: r.get("seq", 0), reverse=True)
    if last is not None:
        records = records[: max(0, last)]
    return records


def clear_dev_mailbox() -> None:
    """Remove all dev-mailbox records (used by QA setup). No-op when disabled."""
    if not is_email_test_mode_enabled():
        return
    with _lock:
        try:
            if MAILBOX_FILE.exists():
                MAILBOX_FILE.write_text("[]", encoding="utf-8")
        except OSError as exc:  # pragma: no cover
            logger.warning("EMAIL_TEST_MODE: could not clear dev mailbox: %s", exc)
