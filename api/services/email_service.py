"""Email sending — config and HTML templates are dashboard-editable.

SMTP settings and templates live in `site_settings` (category `email`) and can
be changed from the admin dashboard. Hardcoded env vars remain as fallbacks so
unwired deployments keep working.
"""
from __future__ import annotations

import logging
import os
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.email_test_mode import (
    is_email_test_mode_enabled,
    write_dev_mailbox_message,
)
from api.services.site_settings import get_effective_settings

logger = logging.getLogger(__name__)

def _int_env(name: str, default: int) -> int:
    """Read an integer environment value without breaking startup on bad input."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


SMTP_HOST = os.getenv("SMTP_HOST") or "mail.privateemail.com"
SMTP_PORT = _int_env("SMTP_PORT", 587)
# SMTP_USERNAME is canonical; SMTP_USER remains supported for existing deployments.
SMTP_USER = os.getenv("SMTP_USERNAME") or os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_SECURITY = (os.getenv("SMTP_SECURITY") or "").strip().lower()
SMTP_TIMEOUT_SECONDS = _int_env("SMTP_TIMEOUT_SECONDS", 15)
SMTP_FROM = os.getenv("SMTP_FROM", "admin@ictfundedeapro.com")
SMTP_REPLY_TO = os.getenv("SMTP_REPLY_TO", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CLIENT_PORTAL_URL = os.getenv("CLIENT_PORTAL_URL") or FRONTEND_URL
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@ictfundedeapro.com")
BILLING_EMAIL = os.getenv("BILLING_EMAIL", "billing@ictfundedeapro.com")


async def _get_config(session: Optional[AsyncSession]) -> Dict[str, Any]:
    """Effective SMTP config: site settings override env defaults."""
    cfg = {
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "smtp_user": SMTP_USER,
        "smtp_pass": SMTP_PASS,
        "smtp_security": SMTP_SECURITY,
        "smtp_timeout_seconds": SMTP_TIMEOUT_SECONDS,
        "smtp_from": SMTP_FROM,
        "smtp_reply_to": SMTP_REPLY_TO,
        "frontend_url": CLIENT_PORTAL_URL,
        "support_address": SUPPORT_EMAIL,
        "billing_address": BILLING_EMAIL,
    }
    if session is None:
        return cfg
    try:
        s = await get_effective_settings(session, decrypt_secrets=True)
    except Exception as e:  # never break sending because settings failed
        logger.warning("Could not load site settings for email: %s", e)
        return cfg
    cfg["smtp_host"] = s.get("email.smtp_host") or cfg["smtp_host"]
    cfg["smtp_port"] = int(s.get("email.smtp_port") or cfg["smtp_port"])
    cfg["smtp_user"] = s.get("email.smtp_username") or s.get("email.smtp_user") or cfg["smtp_user"]
    cfg["smtp_pass"] = s.get("email.smtp_pass") or cfg["smtp_pass"]
    cfg["smtp_security"] = str(s.get("email.smtp_security") or cfg["smtp_security"]).strip().lower()
    try:
        cfg["smtp_timeout_seconds"] = int(s.get("email.smtp_timeout_seconds") or cfg["smtp_timeout_seconds"])
    except (TypeError, ValueError):
        pass
    cfg["smtp_from"] = s.get("email.smtp_from") or cfg["smtp_from"]
    cfg["smtp_reply_to"] = s.get("email.smtp_reply_to") or cfg["smtp_reply_to"]
    cfg["frontend_url"] = (
        s.get("email.client_portal_url")
        or s.get("email.frontend_url")
        or cfg["frontend_url"]
    )
    cfg["support_address"] = s.get("email.support_address") or cfg["support_address"]
    cfg["billing_address"] = s.get("email.billing_address") or cfg["billing_address"]
    return cfg


def _render_template(template: str, variables: Dict[str, Any]) -> str:
    """Replace {placeholder} tokens. Uses str.replace to stay safe with CSS braces."""
    out = template
    for key, value in variables.items():
        out = out.replace("{" + key + "}", str(value))
    return out


async def _get_template(session: Optional[AsyncSession], key: str) -> str:
    if session is None:
        return ""
    try:
        s = await get_effective_settings(session, decrypt_secrets=False)
    except Exception:
        return ""
    return str(s.get(key) or "")


def _wrap_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#0f172a;padding:40px 20px">
<div style="max-width:480px;margin:auto;background:#1e293b;border-radius:12px;padding:32px;border:1px solid #334155">
<div style="text-align:center;margin-bottom:24px">
<h1 style="color:#f1f5f9;font-size:20px;margin:0">ICT EA Pro</h1>
<p style="color:#94a3b8;font-size:12px;margin:4px 0 0">Algorithmic Trading Platform</p>
</div>
<div style="color:#f1f5f9;font-size:14px;line-height:1.6">{body}</div>
<div style="margin-top:24px;padding-top:16px;border-top:1px solid #334155;text-align:center;color:#64748b;font-size:11px">
<p>&copy; 2026 ICT Funded EA Pro. All rights reserved.</p>
<p style="margin:2px 0">support@ictfundedeapro.com</p>
</div></div></body></html>"""


async def send_email(
    to: str,
    subject: str,
    body_text: str,
    session: Optional[AsyncSession] = None,
    template: str = "",
    template_vars: Optional[Dict[str, Any]] = None,
    from_address: Optional[str] = None,
) -> bool:
    """Send a plain-text + HTML email. If a dashboard template is provided it
    replaces the generated HTML (falling back to the default wrapper)."""
    cfg = await _get_config(session)
    delivery_id = uuid.uuid4().hex[:12]
    missing = [
        key for key in ("smtp_host", "smtp_user", "smtp_pass")
        if not cfg.get(key)
    ]
    security = str(cfg.get("smtp_security") or "").lower()
    if not security:
        security = "ssl" if int(cfg["smtp_port"]) == 465 else "starttls"
    if security not in {"ssl", "starttls"}:
        logger.warning(
            "Email delivery configuration failure id=%s reason=invalid_security_mode",
            delivery_id,
        )
        return False
    if missing:
        logger.warning(
            "Email delivery configuration failure id=%s missing=%s",
            delivery_id,
            ",".join(missing),
        )
        return False

    sender = from_address or cfg["smtp_from"]

    html_body = _wrap_html(body_text)
    if template and template.strip():
        rendered = _render_template(template, template_vars or {})
        if rendered.strip():
            html_body = rendered

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = sender
        msg["To"] = to
        msg["Subject"] = subject
        if cfg.get("smtp_reply_to"):
            msg["Reply-To"] = cfg["smtp_reply_to"]
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        smtp_client = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
        with smtp_client(
            cfg["smtp_host"],
            cfg["smtp_port"],
            timeout=cfg["smtp_timeout_seconds"],
        ) as server:
            if security == "starttls":
                server.starttls()
            server.login(cfg["smtp_user"], cfg["smtp_pass"])
            server.send_message(msg)
        logger.info("Email delivery succeeded id=%s", delivery_id)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Email delivery provider failure id=%s category=authentication", delivery_id)
        return False
    except (smtplib.SMTPConnectError, TimeoutError, OSError):
        logger.error("Email delivery provider failure id=%s category=connection", delivery_id)
        return False
    except smtplib.SMTPException as e:
        logger.error(
            "Email delivery provider failure id=%s category=smtp type=%s",
            delivery_id,
            type(e).__name__,
        )
        return False
    except Exception as e:
        logger.error(
            "Email delivery provider failure id=%s category=unexpected type=%s",
            delivery_id,
            type(e).__name__,
        )
        return False


async def send_verification_email(
    to: str, code: str, session: Optional[AsyncSession] = None
) -> bool:
    cfg = await _get_config(session)
    verify_link = f"{cfg['frontend_url']}/verify-email?code={code}"
    body = f"""<h2 style="color:#3b82f6;margin:0 0 12px">Verify Your Email</h2>
<p>Your verification code is:</p>
<div style="background:#0f172a;border-radius:8px;padding:12px;text-align:center;margin:12px 0;font-size:24px;letter-spacing:4px;color:#3b82f6;font-weight:bold">{code}</div>
<p style="color:#94a3b8;font-size:13px">Or click the button below:</p>
<a href="{verify_link}" style="display:inline-block;background:#3b82f6;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Verify Email</a>
<p style="color:#94a3b8;font-size:12px;margin-top:12px">This code expires in 1 hour.</p>"""

    # DEV-ONLY: EMAIL_TEST_MODE writes the code to a local mailbox file instead
    # of SMTP. Never active in production and never when SMTP creds are set —
    # see api/services/email_test_mode.py.
    if is_email_test_mode_enabled():
        if write_dev_mailbox_message(
            to, "Verify Your Email — ICT EA Pro", code, verify_link, kind="verify_email"
        ):
            return True

    return await send_email(to, "Verify Your Email — ICT EA Pro", body, session=session)


async def send_password_reset_email(
    to: str, code: str, session: Optional[AsyncSession] = None
) -> bool:
    cfg = await _get_config(session)
    reset_link = f"{cfg['frontend_url']}/reset-password?code={code}"
    body = f"""<h2 style="color:#f59e0b;margin:0 0 12px">Reset Your Password</h2>
<p>Your password reset code is:</p>
<div style="background:#0f172a;border-radius:8px;padding:12px;text-align:center;margin:12px 0;font-size:24px;letter-spacing:4px;color:#f59e0b;font-weight:bold">{code}</div>
<p style="color:#94a3b8;font-size:13px">Or click the button below:</p>
<a href="{reset_link}" style="display:inline-block;background:#f59e0b;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Reset Password</a>
<p style="color:#94a3b8;font-size:12px;margin-top:12px">This code expires in 1 hour. If you didn't request this, ignore this email.</p>"""
    template = await _get_template(session, "email.template_reset")

    # DEV-ONLY: same mechanism as send_verification_email (see above).
    if is_email_test_mode_enabled():
        if write_dev_mailbox_message(
            to, "Reset Your Password — ICT EA Pro", code, reset_link, kind="reset_password"
        ):
            return True

    return await send_email(
        to, "Reset Your Password — ICT EA Pro", body,
        session=session, template=template, template_vars={"code": code, "link": reset_link},
    )


async def send_welcome_email(
    to: str, first_name: str, session: Optional[AsyncSession] = None
) -> bool:
    cfg = await _get_config(session)
    dashboard_link = f"{cfg['frontend_url']}/dashboard"
    body = f"""<h2 style="color:#22c55e;margin:0 0 12px">Welcome, {first_name}!</h2>
<p>Your account has been created successfully. You can now access your client dashboard to manage your trading accounts, licenses, and subscriptions.</p>
<a href="{dashboard_link}" style="display:inline-block;background:#22c55e;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Go to Dashboard</a>"""
    template = await _get_template(session, "email.template_welcome")
    return await send_email(
        to, "Welcome to ICT EA Pro!", body,
        session=session, template=template,
        template_vars={"first_name": first_name, "link": dashboard_link},
    )


async def send_license_activated_email(
    to: str, first_name: str, license_key: str, session: Optional[AsyncSession] = None
) -> bool:
    """License activation notice — sent from the main/admin address."""
    body = f"""<h2 style="color:#22c55e;margin:0 0 12px">License Activated</h2>
<p>Hello {first_name},</p>
<p>Your license has been activated and your trading bot is ready to go.</p>
<div style="background:#0f172a;border-radius:8px;padding:12px;text-align:center;margin:12px 0;font-family:monospace;color:#22c55e;font-weight:bold">{license_key}</div>
<p style="color:#94a3b8;font-size:12px">If you need any help, our support team is here for you.</p>"""
    template = await _get_template(session, "email.template_license")
    return await send_email(
        to, "License Activated — ICT EA Pro", body,
        session=session, template=template,
        template_vars={"first_name": first_name, "license_key": license_key},
    )


async def send_account_connected_email(
    to: str,
    first_name: str,
    platform: str,
    login: str,
    broker: str,
    account_type: str,
    session: Optional[AsyncSession] = None,
) -> bool:
    """Notify the client when an MT5 trading account is successfully connected."""
    cfg = await _get_config(session)
    body = f"""<h2 style="color:#22c55e;margin:0 0 12px">Trading Account Connected</h2>
<p>Hello {first_name},</p>
<p>Your <b>{platform}</b> trading account has been successfully connected and verified.</p>
<div style="background:#0f172a;border-radius:8px;padding:16px;margin:12px 0;color:#e2e8f0;font-size:13px">
<p><b>Account:</b> {login}</p>
<p><b>Broker:</b> {broker}</p>
<p><b>Type:</b> {account_type}</p>
</div>
<p style="color:#94a3b8;font-size:13px">The trading engine is now active on this account. You can manage it from your dashboard.</p>
<a href="{cfg['frontend_url']}/dashboard/accounts" style="display:inline-block;background:#22c55e;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">View My Accounts</a>"""
    template = await _get_template(session, "email.template_license")
    return await send_email(
        to, "Trading Account Connected — ICT EA Pro", body,
        session=session, template=template,
        template_vars={"first_name": first_name, "platform": platform, "login": login, "broker": broker, "account_type": account_type},
    )


async def send_payment_success_email(
    to: str, amount: str, plan: str, session: Optional[AsyncSession] = None
) -> bool:
    """Payment confirmation — sent from the billing address."""
    cfg = await _get_config(session)
    body = f"""<h2 style="color:#22c55e;margin:0 0 12px">Payment Received</h2>
<p>Thank you! Your payment of <b>{amount}</b> for <b>{plan}</b> has been received.</p>
<p style="color:#94a3b8;font-size:13px">You can view your invoices from your client dashboard.</p>"""
    template = await _get_template(session, "email.template_payment")
    return await send_email(
        to, "Payment Received — ICT EA Pro", body,
        session=session, template=template,
        template_vars={"amount": amount, "plan": plan},
        from_address=cfg["billing_address"],
    )


async def send_subscription_expiring_email(
    to: str, days_left: int, session: Optional[AsyncSession] = None
) -> bool:
    """Subscription renewal reminder — sent from the billing address."""
    cfg = await _get_config(session)
    body = f"""<h2 style="color:#f59e0b;margin:0 0 12px">Subscription Expiring Soon</h2>
<p>Your subscription expires in <b>{days_left} day{'s' if days_left != 1 else ''}</b>.</p>
<p style="color:#94a3b8;font-size:13px">Renew now to keep your trading bot running without interruption.</p>"""
    template = await _get_template(session, "email.template_expiring")
    return await send_email(
        to, "Subscription Expiring Soon — ICT EA Pro", body,
        session=session, template=template,
        template_vars={"days_left": days_left},
        from_address=cfg["billing_address"],
    )


async def send_subscription_expired_email(
    to: str, session: Optional[AsyncSession] = None
) -> bool:
    """Subscription expired notice — sent from the billing address."""
    cfg = await _get_config(session)
    body = f"""<h2 style="color:#ef4444;margin:0 0 12px">Subscription Expired</h2>
<p>Your subscription has expired. Trading on your accounts has been paused.</p>
<p style="color:#94a3b8;font-size:13px">Renew your subscription to reactivate your bot.</p>"""
    template = await _get_template(session, "email.template_expired")
    return await send_email(
        to, "Subscription Expired — ICT EA Pro", body,
        session=session, template=template,
        from_address=cfg["billing_address"],
    )


async def send_manual_payment_instructions_email(
    to: str,
    first_name: str,
    plan_name: str,
    amount: str,
    currency: str,
    instructions: str,
    payment_number: str,
    session: Optional[AsyncSession] = None,
) -> bool:
    """Send manual payment instructions to client after checkout creation."""
    cfg = await _get_config(session)
    body = f"""<h2 style="color:#3b82f6;margin:0 0 12px">Complete Your Payment</h2>
<p>Hello {first_name},</p>
<p>Your order <b>{payment_number}</b> for <b>{plan_name}</b> ({amount} {currency}) is ready.</p>
<h3 style="color:#f1f5f9;font-size:14px;margin:16px 0 8px">Payment Instructions</h3>
<div style="background:#0f172a;border-radius:8px;padding:16px;color:#e2e8f0;font-size:13px;white-space:pre-wrap;line-height:1.6">{instructions}</div>
<p style="color:#94a3b8;font-size:13px;margin-top:16px">After completing the payment, please submit your payment reference from your dashboard so we can verify and activate your subscription.</p>
<a href="{cfg['frontend_url']}/dashboard/subscription" style="display:inline-block;background:#3b82f6;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Go to Dashboard</a>"""
    return await send_email(
        to, f"Payment Instructions — {payment_number}", body,
        session=session, from_address=cfg["billing_address"],
    )


async def send_manual_payment_submitted_email(
    to: str,
    client_name: str,
    payment_number: str,
    plan_name: str,
    amount: str,
    currency: str,
    reference: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> bool:
    """Notify billing/owner when a client submits a manual payment for verification."""
    ref_section = f"<p><b>Reference:</b> {reference}</p>" if reference else ""
    body = f"""<h2 style="color:#f59e0b;margin:0 0 12px">Manual Payment Pending Verification</h2>
<p>A client has submitted a manual payment that requires your review.</p>
<div style="background:#0f172a;border-radius:8px;padding:16px;margin:12px 0;color:#e2e8f0;font-size:13px">
<p><b>Payment:</b> {payment_number}</p>
<p><b>Client:</b> {client_name}</p>
<p><b>Plan:</b> {plan_name}</p>
<p><b>Amount:</b> {amount} {currency}</p>
{ref_section}</div>
<p style="color:#94a3b8;font-size:13px">Review and approve or reject this payment from the Owner Portal.</p>
<a href="{cfg['frontend_url'].replace(':3000', ':3002')}/billing" style="display:inline-block;background:#f59e0b;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Review Payment</a>"""
    return await send_email(
        to, f"Payment Pending Verification — {payment_number}", body,
        session=session, from_address=cfg["billing_address"],
    )


async def send_manual_payment_approved_email(
    to: str,
    first_name: str,
    payment_number: str,
    plan_name: str,
    amount: str,
    currency: str,
    session: Optional[AsyncSession] = None,
) -> bool:
    """Notify client when their manual payment is approved and subscription activated."""
    cfg = await _get_config(session)
    body = f"""<h2 style="color:#22c55e;margin:0 0 12px">Payment Approved</h2>
<p>Hello {first_name},</p>
<p>Your payment <b>{payment_number}</b> of <b>{amount} {currency}</b> for <b>{plan_name}</b> has been approved.</p>
<p style="color:#22c55e;font-size:14px;font-weight:bold;margin:12px 0">Your subscription is now active!</p>
<p style="color:#94a3b8;font-size:13px">You can access your trading dashboard and download your EA builds.</p>
<a href="{cfg['frontend_url']}/dashboard" style="display:inline-block;background:#22c55e;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Go to Dashboard</a>"""
    return await send_email(
        to, "Payment Approved — Subscription Active — ICT EA Pro", body,
        session=session, from_address=cfg["billing_address"],
    )


async def send_manual_payment_rejected_email(
    to: str,
    first_name: str,
    payment_number: str,
    plan_name: str,
    amount: str,
    currency: str,
    reason: str,
    session: Optional[AsyncSession] = None,
) -> bool:
    """Notify client when their manual payment is rejected."""
    cfg = await _get_config(session)
    body = f"""<h2 style="color:#ef4444;margin:0 0 12px">Payment Not Verified</h2>
<p>Hello {first_name},</p>
<p>Your payment <b>{payment_number}</b> of <b>{amount} {currency}</b> for <b>{plan_name}</b> could not be verified.</p>
<div style="background:#0f172a;border-radius:8px;padding:12px;margin:12px 0;color:#fca5a5;font-size:13px">
<b>Reason:</b> {reason}
</div>
<p style="color:#94a3b8;font-size:13px">If you believe this is an error, please contact our support team or try again.</p>
<a href="{cfg['frontend_url']}/dashboard/subscription" style="display:inline-block;background:#3b82f6;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Try Again</a>"""
    return await send_email(
        to, f"Payment Not Verified — {payment_number}", body,
        session=session, from_address=cfg["billing_address"],
    )


async def send_subscription_activated_email(
    to: str,
    first_name: str,
    plan_name: str,
    subscription_number: str,
    end_date: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> bool:
    """Notify client when their subscription becomes active."""
    cfg = await _get_config(session)
    expiry_line = f"<p><b>Valid until:</b> {end_date}</p>" if end_date else ""
    body = f"""<h2 style="color:#22c55e;margin:0 0 12px">Subscription Activated</h2>
<p>Hello {first_name},</p>
<p>Your subscription <b>{subscription_number}</b> for <b>{plan_name}</b> is now active.</p>
{expiry_line}
<p style="color:#94a3b8;font-size:13px">You can now download your EA builds and configure your trading bot.</p>
<a href="{cfg['frontend_url']}/dashboard" style="display:inline-block;background:#22c55e;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Go to Dashboard</a>"""
    return await send_email(
        to, "Subscription Activated — ICT EA Pro", body,
        session=session, from_address=cfg["billing_address"],
    )


async def send_payment_failed_email(
    to: str,
    first_name: str,
    payment_number: str,
    plan_name: str,
    amount: str,
    currency: str,
    reason: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> bool:
    """Notify client when a payment fails."""
    cfg = await _get_config(session)
    reason_style = "color:#fca5a5;font-size:13px"
    reason_section = f'<p style="{reason_style}"><b>Reason:</b> {reason}</p>' if reason else ""
    body = f"""<h2 style="color:#ef4444;margin:0 0 12px">Payment Failed</h2>
<p>Hello {first_name},</p>
<p>Your payment <b>{payment_number}</b> of <b>{amount} {currency}</b> for <b>{plan_name}</b> was not successful.</p>
{reason_section}
<p style="color:#94a3b8;font-size:13px">Your subscription has not been activated. You can try again from your dashboard.</p>
<a href="{cfg['frontend_url']}/dashboard/subscription" style="display:inline-block;background:#3b82f6;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Try Again</a>"""
    return await send_email(
        to, f"Payment Failed — {payment_number}", body,
        session=session, from_address=cfg["billing_address"],
    )


async def send_payment_expired_email(
    to: str,
    first_name: str,
    payment_number: str,
    plan_name: str,
    amount: str,
    currency: str,
    session: Optional[AsyncSession] = None,
) -> bool:
    """Notify client when their manual payment window expired (REQ 7)."""
    cfg = await _get_config(session)
    body = f"""<h2 style="color:#f59e0b;margin:0 0 12px">Payment Window Expired</h2>
<p>Hello {first_name},</p>
<p>Your payment <b>{payment_number}</b> of <b>{amount} {currency}</b> for <b>{plan_name}</b> expired before it was submitted for verification.</p>
<p style="color:#94a3b8;font-size:13px">No money was charged. If you already sent the transfer, please contact support with your payment reference.</p>
<a href="{cfg['frontend_url']}/dashboard/subscription" style="display:inline-block;background:#f59e0b;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:14px;margin:8px 0">Create a New Payment</a>"""
    return await send_email(
        to, f"Payment Expired — {payment_number}", body,
        session=session, from_address=cfg["billing_address"],
    )


async def notify_support_ticket(
    subject: str, body: str, session: Optional[AsyncSession] = None,
    client_ref: str = "", category: str = "other",
) -> bool:
    """Forward a new client ticket to the support inbox."""
    cfg = await _get_config(session)
    text = f"""A new support ticket has been created.

{subject}

{body}

Client: {client_ref}
Category: {category}"""
    return await send_email(cfg["support_address"], f"New Ticket — {subject}", text, session=session)


def generate_verification_code() -> str:
    return uuid.uuid4().hex[:8].upper()
