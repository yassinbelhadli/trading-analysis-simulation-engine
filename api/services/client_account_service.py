"""Application service for client MT5 account lifecycle workflows."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.license_service import LicenseService
from core_engine.engine_manager import engine_manager
from database.models import RiskProfile, TradingAccount
from database.repositories import AccountRepository, ScanRepository, UserRepository
from database.repositories.account_repository import AccountNotFoundError as RepositoryAccountNotFoundError
from security.account_fingerprint import build_account_fingerprint
from security.audit import log_event
from security.encryption import decrypt, encrypt
from telegram_bot.services.mt_connector import MTLoginData, mt_connector

logger = logging.getLogger(__name__)


class ClientAccountServiceError(Exception):
    """Base error for client account workflows."""


class AccountInputError(ClientAccountServiceError):
    """The account request contains invalid input."""


class AccountNoActiveLicenseError(ClientAccountServiceError):
    """The user has no active license for account provisioning."""


class AccountLimitReachedError(ClientAccountServiceError):
    """The user's license account limit has been reached."""


class AccountAlreadyLinkedError(ClientAccountServiceError):
    """The account is already linked to the current user."""


class AccountLinkedToAnotherUserError(ClientAccountServiceError):
    """The account is already linked to another user."""


class ClientAccountNotFoundError(ClientAccountServiceError):
    """The account does not exist or is not owned by the current user."""


class AccountConnectionError(ClientAccountServiceError):
    """The MT5 credential verification failed."""


class AccountCredentialsError(ClientAccountServiceError):
    """Stored credentials are unavailable for reconnect."""


class ClientAccountService:
    """Coordinate client account persistence, scanning, and engine lifecycle."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repository = AccountRepository(session)
        self.scan_repository = ScanRepository(session)
        self.license_service = LicenseService(session)

    async def list_accounts(self, user_id: str) -> dict[str, Any]:
        """List visible accounts and the user's current account limits."""
        accounts = [
            account
            for account in await self.account_repository.get_by_user_id(user_id)
            if account.removed_at is None
        ]
        accounts.sort(
            key=lambda account: account.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        items = [await self._account_payload(account) for account in accounts]
        limits = await self.license_service.get_account_limits(user_id)
        return {"items": items, "total": len(items), "limits": limits}

    async def add_account(self, user_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Validate, scan, persist, audit, and start a client account."""
        platform = str(body.get("platform") or "").upper().strip()
        server = str(body.get("server") or "").strip()
        login = str(body.get("login") or "").strip()
        password = str(body.get("password") or "")
        name = str(body.get("name") or "").strip()
        account_type = str(body.get("account_type") or "").upper().strip()

        if not platform or not server or not login or not password:
            raise AccountInputError("platform, server, login and password are required")
        # MT5-only product: MT4 is no longer supported. Reject any non-MT5
        # platform explicitly so legacy clients cannot provision MT4 accounts.
        if platform != "MT5":
            raise AccountInputError("Unsupported platform. Only MT5 is supported")
        if not login.isdigit():
            raise AccountInputError("Account number (login) must contain only digits")

        license_row = await self.license_service.get_active_license(user_id)
        if license_row is None:
            raise AccountNoActiveLicenseError("No active license. Purchase or activate a license first")

        limits = await self.license_service.get_account_limits(user_id, license_row.id)
        if not limits["unlimited"] and limits["used"] >= limits["max"]:
            raise AccountLimitReachedError(f"Max accounts ({limits['max']}) reached for your plan")

        fingerprint = build_account_fingerprint(platform=platform, server=server, login=login)
        existing = await self.account_repository.get_bound_by_fingerprint(fingerprint)
        if existing:
            if existing.user_id == user_id:
                raise AccountAlreadyLinkedError("This account is already linked to your account")
            raise AccountLinkedToAnotherUserError("This account is linked to another user")

        scan = await mt_connector.test_connection(MTLoginData(
            platform=platform,
            server=server,
            login=login,
            password=password,
        ))
        if not scan.success:
            logger.warning("MT connection failed state=%s login=%s", scan.state, login)
            raise AccountConnectionError(scan.message)

        # Accept user-provided account_type (PERSONAL / FUNDED) with
        # auto-inference fallback based on detected trade mode.
        valid_types = {"PERSONAL", "FUNDED", "CHALLENGE", "UNKNOWN"}
        if account_type not in valid_types:
            account_type = "FUNDED" if scan.trade_mode and scan.trade_mode not in ("DEMO", "UNKNOWN") else "PERSONAL"

        account = TradingAccount(
            user_id=user_id,
            account_type=account_type,
            broker=scan.broker_name,
            platform=platform,
            server=server,
            login=login,
            encrypted_password=encrypt(password),
            name=name or None,
            account_size=scan.account_balance or None,
            demo_real=("DEMO" if scan.trade_mode == "DEMO" else "REAL"),
            trade_mode=scan.trade_mode or "DEMO",
            currency=scan.account_currency or "USD",
            leverage=scan.leverage or None,
            balance_snapshot=scan.account_balance,
            equity_snapshot=scan.account_equity,
            symbol_mapping={"symbols": scan.detected_symbols[:50]},
            account_fingerprint=fingerprint,
            verified=True,
            active=True,
            engine_status="ACTIVE",
            license_id=license_row.id,
        )
        await self.account_repository.create_client_account(
            account,
            RiskProfile(
                mode="balanced",
                drawdown_type="static",
                initial_balance=scan.account_balance,
            ),
        )
        await self.scan_repository.create(
            account_id=account.id,
            broker_detected=scan.broker_name,
            balance_detected=scan.account_balance,
            equity_detected=scan.account_equity,
            leverage_detected=scan.leverage,
            symbols_detected=",".join(scan.detected_symbols[:50]),
            scan_status="success",
        )
        await log_event(
            self.session,
            "account.added",
            "Client added MT account",
            user_id=user_id,
            account_id=account.id,
        )
        await self.session.commit()

        try:
            await engine_manager.start(account.id)
        except Exception:
            logger.warning("engine auto-start skipped for %s", account.id)

        # Notify the client that their MT5 account was connected (REQ 15).
        try:
            user = await UserRepository(self.session).get_by_id(user_id)
            if user and user.email:
                from api.services.email_service import send_account_connected_email
                await send_account_connected_email(
                    user.email,
                    user.first_name or "Trader",
                    platform=account.platform or "MT5",
                    login=account.login or "",
                    broker=account.broker or "Unknown",
                    account_type=account.account_type or "PERSONAL",
                    session=self.session,
                )
        except Exception:
            logger.warning("account-connected email skipped for user=%s", user_id)

        return {"message": "Account connected", "account": await self._account_payload(account)}

    async def rename_account(self, user_id: str, account_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Rename an owned account without changing its connection state."""
        account = await self._owned_account(user_id, account_id)
        name = str(body.get("name") or "").strip()
        if not name:
            raise AccountInputError("Name cannot be empty")
        if len(name) > 60:
            raise AccountInputError("Name too long (max 60 chars)")
        account.name = name
        await log_event(
            self.session,
            "account.renamed",
            "Client renamed account",
            user_id=user_id,
            account_id=account.id,
        )
        await self.session.commit()
        return {"message": "Account renamed", "account": await self._account_payload(account)}

    async def remove_account(self, user_id: str, account_id: str) -> dict[str, str]:
        """Soft-remove an owned account after stopping its engine."""
        await self._owned_account(user_id, account_id)
        try:
            await engine_manager.stop(account_id)
        except Exception:
            logger.warning("engine stop skipped for %s", account_id)
        try:
            await self.account_repository.remove_account(account_id, user_id)
        except RepositoryAccountNotFoundError as exc:
            raise ClientAccountNotFoundError("Account not found") from exc
        await log_event(
            self.session,
            "account.removed",
            "Client removed account",
            user_id=user_id,
            account_id=account_id,
        )
        await self.session.commit()
        return {"message": "Account removed"}

    async def disconnect_account(self, user_id: str, account_id: str) -> dict[str, Any]:
        """Stop an owned account while keeping it available for reconnect."""
        account = await self._owned_account(user_id, account_id)
        try:
            await engine_manager.stop(account_id)
        except Exception:
            pass
        account.engine_status = "STOPPED"
        await log_event(
            self.session,
            "account.disconnected",
            "Client disconnected account",
            user_id=user_id,
            account_id=account.id,
        )
        await self.session.commit()
        return {"message": "Account disconnected", "account": await self._account_payload(account)}

    async def reconnect_account(
        self,
        user_id: str,
        account_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Revalidate credentials and refresh an owned account snapshot."""
        account = await self._owned_account(user_id, account_id)
        password = str(body.get("password") or "")
        if not account.encrypted_password and not password:
            raise AccountCredentialsError("No stored credentials. Provide the account password")

        try:
            stored_password = decrypt(account.encrypted_password) if account.encrypted_password else ""
            password_to_test = password or stored_password
        except Exception:
            password_to_test = password

        scan = await mt_connector.test_connection(MTLoginData(
            platform=account.platform or "MT5",
            server=account.server or "",
            login=account.login or "",
            password=password_to_test or "",
        ))
        if not scan.success:
            logger.warning("MT reconnection failed state=%s login=%s", scan.state, account.login)
            raise AccountConnectionError(scan.message)

        account.balance_snapshot = scan.account_balance
        account.equity_snapshot = scan.account_equity
        account.broker = scan.broker_name or account.broker
        account.engine_status = "ACTIVE"
        account.active = True
        account.verified = True
        await self.scan_repository.create(
            account_id=account.id,
            broker_detected=scan.broker_name,
            balance_detected=scan.account_balance,
            equity_detected=scan.account_equity,
            symbols_detected=",".join(scan.detected_symbols[:50]),
            scan_status="success",
        )
        await log_event(
            self.session,
            "account.reconnected",
            "Client reconnected account",
            user_id=user_id,
            account_id=account_id,
        )
        await self.session.commit()

        try:
            await engine_manager.start(account_id)
        except Exception:
            logger.warning("engine auto-start skipped for %s", account_id)

        return {"message": "Account reconnected", "account": await self._account_payload(account)}

    async def _owned_account(self, user_id: str, account_id: str) -> TradingAccount:
        """Load an active owned account or raise the route-compatible error."""
        account = await self.account_repository.get_by_id(account_id)
        if not account or account.user_id != user_id or account.removed_at is not None:
            raise ClientAccountNotFoundError("Account not found")
        return account

    async def _account_payload(self, account: TradingAccount) -> dict[str, Any]:
        """Build the existing client account response payload."""
        scan = await self.scan_repository.get_latest_by_account(account.id)
        connected = engine_manager.is_running(account.id) or account.engine_status == "ACTIVE"
        return {
            "id": account.id,
            "name": account.name or account.login or account.id[:8],
            "platform": account.platform,
            "server": account.server,
            "login": account.login,
            "broker": account.broker or account.prop_firm or "—",
            "account_type": account.account_type,
            "engine_status": account.engine_status,
            "active": account.active,
            "verified": account.verified,
            "balance": account.balance_snapshot,
            "equity": account.equity_snapshot,
            "currency": account.currency or "USD",
            "leverage": account.leverage,
            "demo_real": account.demo_real or account.trade_mode,
            "account_size": account.account_size,
            "license_id": account.license_id,
            "connected": connected,
            "last_sync": (
                scan.scanned_at.isoformat() if scan and scan.scanned_at
                else account.created_at.isoformat() if account.created_at else None
            ),
            "created_at": account.created_at.isoformat() if account.created_at else None,
        }
