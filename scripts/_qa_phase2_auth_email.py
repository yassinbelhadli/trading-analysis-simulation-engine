"""Mocked SMTP regression checks for Phase 2.2 email delivery."""
from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services import email_service


class FakeSMTP:
    """Small context-manager SMTP double that records delivery behavior."""

    instances: list["FakeSMTP"] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.starttls_called = False
        self.login_args = None
        self.message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        self.starttls_called = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.message = message


def _check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def _decoded_message(message) -> str:
    """Read decoded plain and HTML MIME parts for stable link assertions."""
    parts = message.get_payload()
    if not isinstance(parts, list):
        return message.get_payload(decode=True).decode("utf-8", errors="replace")
    return "\n".join(
        part.get_payload(decode=True).decode("utf-8", errors="replace")
        for part in parts
    )


def _base_config() -> dict[str, object]:
    return {
        "SMTP_HOST": "mail.privateemail.com",
        "SMTP_PORT": 587,
        "SMTP_USER": "mock-user",
        "SMTP_PASS": "mock-pass",
        "SMTP_SECURITY": "starttls",
        "SMTP_TIMEOUT_SECONDS": 10,
        "SMTP_FROM": "noreply@example.test",
        "SMTP_REPLY_TO": "support@example.test",
        "CLIENT_PORTAL_URL": "https://app.ictfundedeapro.com",
    }


def main() -> int:
    """Run mocked SMTP mode, failure diagnostics, and link-generation checks."""
    original = {
        key: getattr(email_service, key)
        for key in (
            "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_SECURITY",
            "SMTP_TIMEOUT_SECONDS", "SMTP_FROM", "SMTP_REPLY_TO", "CLIENT_PORTAL_URL",
        )
    }
    try:
        for key, value in _base_config().items():
            setattr(email_service, key, value)

        FakeSMTP.instances.clear()
        fake_starttls = FakeSMTP()
        with patch.object(email_service.smtplib, "SMTP", return_value=fake_starttls) as smtp_constructor:
            result = asyncio.run(email_service.send_email(
                "client@example.test", "Test subject", "Test body"
            ))
        _check(result is True, "STARTTLS delivery returns true")
        _check(fake_starttls.starttls_called, "STARTTLS mode calls starttls")
        _check(fake_starttls.login_args == ("mock-user", "mock-pass"), "SMTP credentials are passed to provider")
        _check(smtp_constructor.call_args.kwargs.get("timeout") == 10, "SMTP timeout is configured")
        _check(fake_starttls.message["Reply-To"] == "support@example.test", "Reply-To is configurable")

        fake_ssl = FakeSMTP()
        email_service.SMTP_PORT = 465
        email_service.SMTP_SECURITY = "ssl"
        with patch.object(email_service.smtplib, "SMTP_SSL", return_value=fake_ssl) as ssl_constructor:
            result = asyncio.run(email_service.send_email(
                "client@example.test", "SSL subject", "SSL body"
            ))
        _check(result is True, "SSL delivery returns true")
        _check(not fake_ssl.starttls_called, "SSL mode does not call STARTTLS")
        _check(ssl_constructor.call_args.args[:2] == ("mail.privateemail.com", 465), "SSL host and port are correct")

        email_service.SMTP_PASS = ""
        with patch.object(email_service.smtplib, "SMTP") as smtp_constructor:
            result = asyncio.run(email_service.send_email(
                "client@example.test", "Config subject", "Config body"
            ))
        _check(result is False, "Missing SMTP password returns false")
        _check(not smtp_constructor.called, "Missing SMTP password does not open a connection")

        email_service.SMTP_PASS = "mock-pass"
        email_service.SMTP_PORT = 587
        email_service.SMTP_SECURITY = "starttls"
        error_stream = io.StringIO()
        handler = logging.StreamHandler(error_stream)
        logger = logging.getLogger("api.services.email_service")
        logger.addHandler(handler)
        try:
            with patch.object(email_service.smtplib, "SMTP", side_effect=OSError("network unavailable")):
                result = asyncio.run(email_service.send_email(
                    "client@example.test", "Network subject", "Network body"
                ))
        finally:
            logger.removeHandler(handler)
        _check(result is False, "Provider connection failure returns false")
        _check("provider failure" in error_stream.getvalue(), "Provider failure has safe diagnostic category")

        fake_link = FakeSMTP()
        with patch.object(email_service.smtplib, "SMTP", return_value=fake_link):
            result = asyncio.run(email_service.send_verification_email(
                "client@example.test", "ABC12345"
            ))
        message_text = _decoded_message(fake_link.message)
        _check(result is True, "Verification email uses centralized sender")
        _check("app.ictfundedeapro.com/verify-email" in message_text and "ABC12345" in message_text,
               "Verification link uses the Client Portal URL and code")

        fake_reset = FakeSMTP()
        with patch.object(email_service.smtplib, "SMTP", return_value=fake_reset):
            result = asyncio.run(email_service.send_password_reset_email(
                "client@example.test", "RESET123"
            ))
        _check(result is True, "Password reset email uses centralized sender")
        reset_text = _decoded_message(fake_reset.message)
        _check("app.ictfundedeapro.com/reset-password" in reset_text and "RESET123" in reset_text,
               "Password reset link uses the Client Portal URL and code")
    finally:
        for key, value in original.items():
            setattr(email_service, key, value)

    print("Phase 2.2 mocked email QA: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
