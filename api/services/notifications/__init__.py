"""Notification pipeline skeleton (Phase 6.0).

Event → Rule → Channel → Recipient → Template → Delivery → Audit

This package owns the neutral notification pipeline shared by Telegram and
Email channels. It intentionally performs NO I/O at import time and never
starts itself — Phase 6.2 wires the dispatcher into the production runtimes.
"""
from __future__ import annotations

from api.services.notifications.channels import (  # noqa: F401
    AuditChannel,
    BaseChannel,
    ChannelResult,
    EmailChannel,
    TelegramChannel,
    channel_registry,
)
from api.services.notifications.dispatcher import (  # noqa: F401
    NotificationDispatcher,
    notification_dispatcher,
)
from api.services.notifications.preferences import (  # noqa: F401
    DEFAULT_NOTIFICATIONS,
    NOTIF_KEYS,
    get_user_notifications,
    wants_notification,
)
from api.services.notifications.rules import (  # noqa: F401
    EMAIL_EVENTS,
    TELEGRAM_PREF_KEYS,
    resolve_channels,
)
from api.services.notifications.templates import (  # noqa: F401
    render_email_body,
    render_email_subject,
    render_telegram,
)

__all__ = [
    "AuditChannel",
    "BaseChannel",
    "ChannelResult",
    "DEFAULT_NOTIFICATIONS",
    "EMAIL_EVENTS",
    "EmailChannel",
    "NOTIF_KEYS",
    "NotificationDispatcher",
    "TelegramChannel",
    "TELEGRAM_PREF_KEYS",
    "channel_registry",
    "get_user_notifications",
    "notification_dispatcher",
    "render_email_body",
    "render_email_subject",
    "render_telegram",
    "resolve_channels",
    "wants_notification",
]
