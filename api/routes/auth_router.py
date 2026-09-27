from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from email_validator import EmailNotValidError, validate_email as validate_email_str
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import LoginSession, Role, User, VerificationToken
from security.auth import (
    create_access_token,
    create_refresh_token,
    create_2fa_token,
    decode_token,
    get_current_user,
    get_optional_user,
    get_user_permissions,
    hash_password,
    hash_refresh_token,
    has_permission,
    log_event,
    seed_roles_and_permissions,
    verify_password,
)
from api.services.email_service import (
    send_verification_email,
    send_password_reset_email,
    send_welcome_email,
    generate_verification_code,
)
from api.services.rate_limit import rate_limit
from security.jwt_handler import REFRESH_TOKEN_EXPIRE_DAYS, SESSION_EXPIRE_DAYS
from security.encryption import decrypt as decrypt_secret, encrypt as encrypt_secret
from security.totp import build_otpauth_uri, generate_totp_secret, verify_totp

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _role_name(user: User) -> str:
    return user.role_rel.name if user.role_rel else "client"


def _decrypt_2fa_secret(stored: str) -> str:
    if stored.startswith("enc:"):
        return decrypt_secret(stored[4:])
    return stored


def _redirect_for(role_name: str) -> str:
    redirect_map = {
        "owner": "/dashboard",
        "admin": "/dashboard",
        "support": "/dashboard",
        "analyst": "/dashboard",
        "risk_manager": "/dashboard",
        "billing": "/dashboard",
        "notification_mgr": "/dashboard",
        "client": "/dashboard",
    }
    return redirect_map.get(role_name, "/dashboard")


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------
@auth_router.post("/login")
async def login(
    request: Request,
    body: dict,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit(limit=10, window_seconds=900)),
):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.account_status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")

    if not user.email_verified:
        try:
            code = generate_verification_code()
            expires = datetime.now(timezone.utc) + timedelta(hours=1)
            result = await session.execute(
                select(VerificationToken).where(
                    VerificationToken.user_id == user.id,
                    VerificationToken.type == "verify_email",
                    VerificationToken.used == False,
                )
            )
            for t in result.scalars().all():
                t.used = True
            session.add(VerificationToken(
                user_id=user.id, code=code, type="verify_email", expires_at=expires,
            ))
            await session.commit()
            sent = await send_verification_email(user.email, code, session=session)
        except Exception:
            sent = False
        if sent:
            raise HTTPException(
                status_code=403,
                detail="Email not verified. A new verification code has been sent to your email.",
            )
        raise HTTPException(
            status_code=403,
            detail="Email not verified. We could not send a verification code right now — please contact support.",
        )

    user.last_login = datetime.now(timezone.utc)

    role_name = _role_name(user)
    redirect_to = _redirect_for(role_name)
    permissions = await get_user_permissions(session, user)

    remember_me = bool(body.get("remember_me"))
    refresh_days = REFRESH_TOKEN_EXPIRE_DAYS if remember_me else SESSION_EXPIRE_DAYS

    if user.two_factor_enabled:
        return {
            "two_factor_required": True,
            "two_factor_token": create_2fa_token(user.id, role=role_name),
            "expires_in": 300,
            "email": user.email,
            "redirect_to": redirect_to,
        }

    access_token = create_access_token(user.id, role=role_name)
    raw_refresh, refresh_hash, refresh_exp = create_refresh_token(user.id, days=refresh_days)

    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    session.add(
        LoginSession(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            ip_address=ip,
            user_agent=ua[:500] if ua else None,
            expires_at=refresh_exp,
        )
    )
    await session.commit()

    await log_event(session, "auth.login", f"User logged in from {ip}",
                    user_id=user.id, payload={"role": role_name, "ip": ip}, commit=True)

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": 1800,
        "remember_me": remember_me,
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": role_name,
            "email_verified": user.email_verified,
            "two_factor_enabled": user.two_factor_enabled,
            "permissions": permissions,
        },
        "redirect_to": redirect_to,
    }


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------
@auth_router.post("/register")
async def register(
    body: dict,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit(limit=5, window_seconds=900)),
):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    first_name = body.get("first_name", "").strip()
    last_name = body.get("last_name", "").strip()

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        validate_email_str(email, check_deliverability=False)
    except EmailNotValidError:
        raise HTTPException(status_code=400, detail="Invalid email format")

    result = await session.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    result = await session.execute(select(Role).where(Role.name == "client"))
    client_role = result.scalar_one_or_none()
    if not client_role:
        await seed_roles_and_permissions(session)
        result = await session.execute(select(Role).where(Role.name == "client"))
        client_role = result.scalar_one_or_none()

    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name or email.split("@")[0],
        last_name=last_name,
        role_id=client_role.id if client_role else None,
        language="EN",
        status="active",
        account_status="active",
        email_verified=False,
    )
    session.add(user)
    await session.commit()

    await log_event(session, "auth.register", f"User registered: {email}",
                    user_id=user.id, commit=True)

    code = generate_verification_code()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    session.add(VerificationToken(
        user_id=user.id,
        code=code,
        type="verify_email",
        expires_at=expires,
    ))
    await session.commit()
    sent = await send_verification_email(user.email, code, session=session)

    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "message": "Registration successful. Please verify your email.",
        "verification_sent": sent,
    }


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------
@auth_router.post("/refresh")
async def refresh_token(
    body: dict,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    raw_refresh = body.get("refresh_token", "")
    if not raw_refresh:
        raise HTTPException(status_code=400, detail="Refresh token is required")

    token_hash = hash_refresh_token(raw_refresh)

    result = await session.execute(
        select(LoginSession).where(
            LoginSession.refresh_token_hash == token_hash,
            LoginSession.is_active == True,
            LoginSession.revoked_at.is_(None),
        )
    )
    login_session = result.scalar_one_or_none()

    if not login_session:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh token")

    if login_session.expires_at < datetime.now(timezone.utc):
        login_session.is_active = False
        await session.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

    login_session.is_active = False
    login_session.revoked_at = datetime.now(timezone.utc)

    result = await session.execute(select(User).where(User.id == login_session.user_id))
    user = result.scalar_one_or_none()
    if not user or user.account_status != "active":
        raise HTTPException(status_code=403, detail="Account not active")

    role_name = user.role_rel.name if user.role_rel else "client"
    access_token = create_access_token(user.id, role=role_name)
    new_raw, new_hash, new_exp = create_refresh_token(user.id)

    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    session.add(
        LoginSession(
            user_id=user.id,
            refresh_token_hash=new_hash,
            ip_address=ip,
            user_agent=ua[:500] if ua else None,
            expires_at=new_exp,
        )
    )
    await log_event(session, "auth.token_refresh", "Access token refreshed",
                    user_id=user.id, payload={"ip": ip})
    await session.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_raw,
        "token_type": "bearer",
        "expires_in": 1800,
    }


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------
@auth_router.post("/logout")
async def logout(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    user_id = None
    raw_refresh = body.get("refresh_token", "")
    if raw_refresh:
        token_hash = hash_refresh_token(raw_refresh)
        result = await session.execute(
            select(LoginSession).where(
                LoginSession.refresh_token_hash == token_hash,
                LoginSession.is_active == True,
            )
        )
        login_session = result.scalar_one_or_none()
        if login_session:
            user_id = login_session.user_id
            login_session.is_active = False
            login_session.revoked_at = datetime.now(timezone.utc)

    if user_id:
        await log_event(session, "auth.logout", "User logged out", user_id=user_id)
    await session.commit()

    return {"message": "Logged out successfully"}


# ---------------------------------------------------------------------------
# POST /auth/logout-all
# ---------------------------------------------------------------------------
@auth_router.post("/logout-all")
async def logout_all(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(LoginSession).where(
            LoginSession.user_id == current_user.id,
            LoginSession.is_active == True,
        )
    )
    for ls in result.scalars().all():
        ls.is_active = False
        ls.revoked_at = datetime.now(timezone.utc)
    await log_event(session, "auth.logout_all", "All sessions terminated", user_id=current_user.id,
                    severity="WARNING")
    await session.commit()
    return {"message": "All sessions terminated"}


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------
@auth_router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    role_name = current_user.role_rel.name if current_user.role_rel else None

    permissions = await get_user_permissions(session, current_user)

    result = await session.execute(
        select(LoginSession).where(
            LoginSession.user_id == current_user.id,
            LoginSession.is_active == True,
        )
    )
    active_sessions = len(result.scalars().all())

    return {
        "id": current_user.id,
        "email": current_user.email,
        "telegram_id": current_user.telegram_id,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "language": current_user.language,
        "timezone": current_user.timezone,
        "role": role_name,
        "account_status": current_user.account_status,
        "email_verified": current_user.email_verified,
        "two_factor_enabled": current_user.two_factor_enabled,
        "two_factor_pending": bool(current_user.two_factor_secret and not current_user.two_factor_enabled),
        "permissions": permissions,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "active_sessions": active_sessions,
        "has_password": bool(current_user.password_hash),
    }


# ---------------------------------------------------------------------------
# POST /auth/change-password
# ---------------------------------------------------------------------------
@auth_router.post("/change-password")
async def change_password(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    current_password = body.get("current_password", "")
    new_password = body.get("new_password", "")

    if current_user.password_hash:
        if not verify_password(current_password, current_user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
    elif not new_password:
        raise HTTPException(status_code=400, detail="New password is required")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    current_user.password_hash = hash_password(new_password)

    await log_event(session, "auth.password_change", "Password changed", user_id=current_user.id)
    await session.commit()

    result = await session.execute(
        select(LoginSession).where(
            LoginSession.user_id == current_user.id,
            LoginSession.is_active == True,
        )
    )
    for ls in result.scalars().all():
        ls.is_active = False
        ls.revoked_at = datetime.now(timezone.utc)
    await session.commit()

    return {"message": "Password changed successfully. Please login again."}


# ---------------------------------------------------------------------------
# POST /auth/verify-email/send
# ---------------------------------------------------------------------------
@auth_router.post("/verify-email/send")
async def send_verification_email_endpoint(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit(limit=5, window_seconds=900)),
):
    if current_user.email_verified:
        return {"message": "Email already verified"}
    if not current_user.email:
        raise HTTPException(status_code=400, detail="No email on account")

    code = generate_verification_code()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)

    result = await session.execute(
        select(VerificationToken).where(
            VerificationToken.user_id == current_user.id,
            VerificationToken.type == "verify_email",
            VerificationToken.used == False,
        )
    )
    old_tokens = result.scalars().all()
    for t in old_tokens:
        t.used = True

    session.add(VerificationToken(
        user_id=current_user.id,
        code=code,
        type="verify_email",
        expires_at=expires,
    ))
    await session.commit()

    sent = await send_verification_email(current_user.email, code, session=session)
    if not sent:
        logger.warning(
            "SMTP not configured — verification code for user %s not delivered",
            current_user.id,
        )
        return {"message": "Verification email queued (SMTP not configured)"}
    return {"message": "Verification email sent"}


# ---------------------------------------------------------------------------
# POST /auth/verify-email/confirm
# ---------------------------------------------------------------------------
@auth_router.post("/verify-email/confirm")
async def confirm_email(
    body: dict,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit(limit=10, window_seconds=900)),
):
    code = body.get("code", body.get("token", ""))
    if not code:
        raise HTTPException(status_code=400, detail="Verification code is required")

    result = await session.execute(
        select(VerificationToken).where(
            VerificationToken.code == code,
            VerificationToken.type == "verify_email",
            VerificationToken.used == False,
            VerificationToken.expires_at > datetime.now(timezone.utc),
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    token.used = True
    user_result = await session.execute(select(User).where(User.id == token.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.email_verified = True
    await session.commit()
    return {"message": "Email verified successfully"}


# ---------------------------------------------------------------------------
# POST /auth/forgot-password
# ---------------------------------------------------------------------------
@auth_router.post("/forgot-password")
async def forgot_password(
    body: dict,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit(limit=5, window_seconds=900)),
):
    email = body.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    try:
        validate_email_str(email, check_deliverability=False)
    except EmailNotValidError:
        raise HTTPException(status_code=400, detail="Invalid email format")

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return {"message": "If the email exists, a reset code has been sent"}

    code = generate_verification_code()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)

    result = await session.execute(
        select(VerificationToken).where(
            VerificationToken.user_id == user.id,
            VerificationToken.type == "reset_password",
            VerificationToken.used == False,
        )
    )
    old_tokens = result.scalars().all()
    for t in old_tokens:
        t.used = True

    session.add(VerificationToken(
        user_id=user.id,
        code=code,
        type="reset_password",
        expires_at=expires,
    ))
    await session.commit()

    sent = await send_password_reset_email(user.email, code, session=session)
    if not sent:
        logger.warning(
            "SMTP not configured — password reset code for user %s not delivered",
            user.id,
        )
    return {"message": "If the email exists, a reset code has been sent"}


# ---------------------------------------------------------------------------
# POST /auth/reset-password
# ---------------------------------------------------------------------------
@auth_router.post("/reset-password")
async def reset_password(
    body: dict,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit(limit=10, window_seconds=900)),
):
    code = body.get("code", body.get("token", ""))
    new_password = body.get("new_password", "")
    email = body.get("email", "").strip().lower()

    if not code or not new_password:
        raise HTTPException(status_code=400, detail="Code and new password are required")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    result = await session.execute(
        select(VerificationToken).where(
            VerificationToken.code == code,
            VerificationToken.type == "reset_password",
            VerificationToken.used == False,
            VerificationToken.expires_at > datetime.now(timezone.utc),
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    user_result = await session.execute(select(User).where(User.id == token.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    if email and user.email != email:
        raise HTTPException(status_code=400, detail="Email does not match")

    user.password_hash = hash_password(new_password)
    token.used = True

    result = await session.execute(
        select(LoginSession).where(
            LoginSession.user_id == user.id,
            LoginSession.is_active == True,
        )
    )
    for ls in result.scalars().all():
        ls.is_active = False
        ls.revoked_at = datetime.now(timezone.utc)

    await log_event(session, "auth.password_reset", "Password reset completed",
                    user_id=user.id, severity="WARNING")
    await session.commit()
    return {"message": "Password reset successfully. Please login with your new password."}


# ---------------------------------------------------------------------------
# POST /auth/2fa/setup   (self-scoped, password re-auth)
# ---------------------------------------------------------------------------
@auth_router.post("/2fa/setup")
async def setup_2fa(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    current_password = body.get("current_password", "")
    if not current_user.password_hash or not verify_password(current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")

    secret = generate_totp_secret()
    current_user.two_factor_secret = "enc:" + encrypt_secret(secret)
    await log_event(session, "auth.2fa_setup", "2FA secret generated",
                    user_id=current_user.id, severity="WARNING")
    await session.commit()
    return {
        "secret": secret,
        "otpauth_uri": build_otpauth_uri(secret, current_user.email or current_user.id),
        "message": "Scan the QR code with your authenticator app, then confirm a code to enable 2FA.",
    }


# ---------------------------------------------------------------------------
# POST /auth/2fa/enable   (self-scoped)
# ---------------------------------------------------------------------------
@auth_router.post("/2fa/enable")
async def enable_2fa(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    code = body.get("code", "")
    if not current_user.two_factor_secret:
        raise HTTPException(status_code=400, detail="Run /auth/2fa/setup first")
    secret = _decrypt_2fa_secret(current_user.two_factor_secret)
    if not verify_totp(secret, code):
        raise HTTPException(status_code=401, detail="Invalid authentication code")
    current_user.two_factor_enabled = True
    await log_event(session, "auth.2fa_enabled", "2FA enabled",
                    user_id=current_user.id, severity="WARNING")
    await session.commit()
    return {"message": "2FA enabled successfully"}


# ---------------------------------------------------------------------------
# POST /auth/2fa/disable   (self-scoped)
# ---------------------------------------------------------------------------
@auth_router.post("/2fa/disable")
async def disable_2fa(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    code = body.get("code", "")
    if not current_user.two_factor_secret:
        raise HTTPException(status_code=400, detail="2FA is not configured")
    secret = _decrypt_2fa_secret(current_user.two_factor_secret)
    if not verify_totp(secret, code):
        raise HTTPException(status_code=401, detail="Invalid authentication code")
    current_user.two_factor_secret = None
    current_user.two_factor_enabled = False
    await log_event(session, "auth.2fa_disabled", "2FA disabled",
                    user_id=current_user.id, severity="WARNING")
    await session.commit()
    return {"message": "2FA disabled successfully"}


# ---------------------------------------------------------------------------
# POST /auth/2fa/verify   (step 2 of login)
# ---------------------------------------------------------------------------
@auth_router.post("/2fa/verify")
async def verify_2fa_login(
    body: dict,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit(limit=10, window_seconds=900)),
):
    code = body.get("code", "")
    twofa_token = body.get("two_factor_token", "")
    if not code or not twofa_token:
        raise HTTPException(status_code=400, detail="code and two_factor_token are required")
    try:
        payload = decode_token(twofa_token, expected_type="2fa")
    except HTTPException:
        raise HTTPException(status_code=401, detail="2FA session expired, please login again")

    user_id = payload.get("sub")
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.two_factor_enabled or not user.two_factor_secret:
        raise HTTPException(status_code=401, detail="2FA is not enabled for this account")
    if user.account_status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")

    secret = _decrypt_2fa_secret(user.two_factor_secret)
    if not verify_totp(secret, code):
        raise HTTPException(status_code=401, detail="Invalid authentication code")

    role_name = _role_name(user)
    remember_me = bool(body.get("remember_me"))
    refresh_days = REFRESH_TOKEN_EXPIRE_DAYS if remember_me else SESSION_EXPIRE_DAYS
    access_token = create_access_token(user.id, role=role_name)
    raw_refresh, refresh_hash, refresh_exp = create_refresh_token(user.id, days=refresh_days)
    permissions = await get_user_permissions(session, user)

    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    session.add(LoginSession(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        ip_address=ip,
        user_agent=ua[:500] if ua else None,
        expires_at=refresh_exp,
    ))
    await log_event(session, "auth.login_2fa", f"User logged in with 2FA from {ip}",
                    user_id=user.id, payload={"role": role_name, "ip": ip})
    await session.commit()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": 1800,
        "remember_me": remember_me,
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": role_name,
            "email_verified": user.email_verified,
            "two_factor_enabled": user.two_factor_enabled,
            "permissions": permissions,
        },
        "redirect_to": _redirect_for(role_name),
    }


# ---------------------------------------------------------------------------
# GET /auth/sessions   (list own sessions)
# ---------------------------------------------------------------------------
@auth_router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(LoginSession)
        .where(LoginSession.user_id == current_user.id)
        .order_by(LoginSession.created_at.desc())
        .limit(20)
    )
    sessions = [
        {
            "id": ls.id,
            "ip_address": ls.ip_address,
            "user_agent": ls.user_agent,
            "device_info": ls.device_info,
            "created_at": ls.created_at.isoformat() if ls.created_at else None,
            "expires_at": ls.expires_at.isoformat() if ls.expires_at else None,
            "is_active": ls.is_active,
            "revoked_at": ls.revoked_at.isoformat() if ls.revoked_at else None,
        }
        for ls in result.scalars().all()
    ]
    return {"sessions": sessions}


# ---------------------------------------------------------------------------
# DELETE /auth/sessions/{session_id}   (revoke own session)
# ---------------------------------------------------------------------------
@auth_router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(LoginSession).where(
            LoginSession.id == session_id,
            LoginSession.user_id == current_user.id,
        )
    )
    ls = result.scalar_one_or_none()
    if not ls:
        raise HTTPException(status_code=404, detail="Session not found")
    ls.is_active = False
    ls.revoked_at = datetime.now(timezone.utc)
    await log_event(session, "auth.session_revoked", "Session revoked",
                    user_id=current_user.id, severity="WARNING")
    await session.commit()
    return {"message": "Session revoked"}


# ---------------------------------------------------------------------------
# POST /auth/check-permission
# ---------------------------------------------------------------------------
@auth_router.post("/check-permission")
async def check_permission_endpoint(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    resource = body.get("resource", "")
    action = body.get("action", "")
    if not resource or not action:
        raise HTTPException(status_code=400, detail="resource and action are required")
    allowed = await has_permission(session, current_user, f"{resource}.{action}")
    return {"resource": resource, "action": action, "allowed": allowed}
