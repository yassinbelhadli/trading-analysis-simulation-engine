from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Permission as PermissionModel, Role, RolePermission, User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Permission Enum  (type-safe reference for route decorators / dependencies)
# ---------------------------------------------------------------------------
class Permission(str, Enum):
    CLIENTS_READ = "clients.read"
    CLIENTS_CREATE = "clients.create"
    CLIENTS_UPDATE = "clients.update"
    CLIENTS_DELETE = "clients.delete"
    CLIENTS_SUSPEND = "clients.suspend"
    CLIENTS_ACTIVATE = "clients.activate"
    CLIENTS_EXPORT = "clients.export"

    ACCOUNTS_READ = "accounts.read"
    ACCOUNTS_CREATE = "accounts.create"
    ACCOUNTS_UPDATE = "accounts.update"
    ACCOUNTS_DELETE = "accounts.delete"

    SUBSCRIPTIONS_READ = "subscriptions.read"
    SUBSCRIPTIONS_CREATE = "subscriptions.create"
    SUBSCRIPTIONS_UPDATE = "subscriptions.update"
    SUBSCRIPTIONS_CANCEL = "subscriptions.cancel"
    SUBSCRIPTIONS_SUSPEND = "subscriptions.suspend"
    SUBSCRIPTIONS_REVOKE = "subscriptions.revoke"

    COUPONS_READ = "coupons.read"
    COUPONS_CREATE = "coupons.create"
    COUPONS_UPDATE = "coupons.update"
    COUPONS_DELETE = "coupons.delete"

    LICENSES_READ = "licenses.read"
    LICENSES_CREATE = "licenses.create"
    LICENSES_UPDATE = "licenses.update"
    LICENSES_DELETE = "licenses.delete"

    EA_READ = "ea.read"
    EA_PUBLISH = "ea.publish"

    TRADES_READ = "trades.read"
    TRADES_EXPORT = "trades.export"
    VIEW_TRADING = "trades.view"

    ANALYTICS_READ = "analytics.read"

    ENGINE_READ = "engine.read"
    ENGINE_START = "engine.start"
    ENGINE_STOP = "engine.stop"
    ENGINE_RESTART = "engine.restart"
    ENGINE_CONTROL = "engine.control"

    ROLES_READ = "roles.read"
    ROLES_CREATE = "roles.create"
    ROLES_UPDATE = "roles.update"
    ROLES_DELETE = "roles.delete"
    ROLES_ASSIGN = "roles.assign"

    USERS_READ = "users.read"
    USERS_CREATE = "users.create"
    USERS_UPDATE = "users.update"
    USERS_DELETE = "users.delete"

    BILLING_READ = "billing.read"
    BILLING_CREATE = "billing.create"
    BILLING_REFUND = "billing.refund"

    PAYMENTS_READ = "payments.read"
    PAYMENTS_VERIFY = "payments.verify"
    PAYMENTS_UPDATE = "payments.update"
    PAYMENTS_REFUND = "payments.refund"
    PAYMENTS_SUSPEND = "payments.suspend"

    SUPPORT_READ = "support.read"
    SUPPORT_CREATE = "support.create"
    SUPPORT_REPLY = "support.reply"

    TICKETS_READ = "tickets.read"
    TICKETS_UPDATE = "tickets.update"
    TICKETS_ASSIGN = "tickets.assign"
    TICKETS_BAN = "tickets.ban"

    TELEGRAM_SEND = "telegram.send"

    EMAIL_READ = "emails.read"
    EMAIL_SEND = "emails.send"

    AUDIT_READ = "audit.read"

    HEALTH_READ = "health.read"

    ADMIN_DASHBOARD_READ = "admin.dashboard.read"
    ADMIN_OVERVIEW = "admin.overview"

    SYSTEM_HEALTH_READ = "system.health.read"
    SYSTEM_HEALTH_UPDATE = "system.health.update"
    SYSTEM_SETTINGS = "system.settings"
    SYSTEM_SECRETS = "system.secrets"

    SELF_READ = "self.read"
    SELF_UPDATE = "self.update"

    OWNER = "*"


# ---------------------------------------------------------------------------
# Built-in role → permission mapping  (seed data / fallback)
# Role name strings are keys; permission strings are values.
# ---------------------------------------------------------------------------
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "owner": {"*"},
    "admin": {
        Permission.ADMIN_DASHBOARD_READ, Permission.ADMIN_OVERVIEW,
        Permission.CLIENTS_READ, Permission.CLIENTS_CREATE, Permission.CLIENTS_UPDATE,
        Permission.CLIENTS_SUSPEND, Permission.CLIENTS_ACTIVATE, Permission.CLIENTS_EXPORT,
        Permission.ACCOUNTS_READ, Permission.ACCOUNTS_CREATE, Permission.ACCOUNTS_UPDATE,
        Permission.ACCOUNTS_DELETE,
        Permission.SUBSCRIPTIONS_READ, Permission.SUBSCRIPTIONS_CREATE,
        Permission.SUBSCRIPTIONS_UPDATE, Permission.SUBSCRIPTIONS_CANCEL,
        Permission.SUBSCRIPTIONS_SUSPEND, Permission.SUBSCRIPTIONS_REVOKE,
        Permission.COUPONS_READ, Permission.COUPONS_CREATE,
        Permission.COUPONS_UPDATE,
        Permission.LICENSES_READ, Permission.LICENSES_CREATE,
        Permission.LICENSES_UPDATE, Permission.LICENSES_DELETE,
        # NOTE: trading read/control (TRADES_READ, VIEW_TRADING, ENGINE_READ,
        # ENGINE_CONTROL) and roles management (ROLES_*) are OWNER-only —
        # enforced by require_role("owner") on /api/admin/trading/* and
        # /api/admin/roles/*. ENGINE_START/STOP/RESTART remain for ops
        # (system-health engine restart is an operations task).
        Permission.ANALYTICS_READ,
        Permission.ENGINE_START, Permission.ENGINE_STOP, Permission.ENGINE_RESTART,
        Permission.USERS_READ, Permission.USERS_CREATE, Permission.USERS_UPDATE,
        Permission.USERS_DELETE,
        Permission.SYSTEM_HEALTH_READ, Permission.SYSTEM_HEALTH_UPDATE,
        Permission.HEALTH_READ,
        Permission.AUDIT_READ,
        Permission.EA_READ, Permission.EA_PUBLISH,
        Permission.SUPPORT_READ, Permission.SUPPORT_CREATE, Permission.SUPPORT_REPLY,
        Permission.BILLING_READ, Permission.BILLING_CREATE,
        Permission.PAYMENTS_READ, Permission.PAYMENTS_VERIFY,
        Permission.PAYMENTS_UPDATE, Permission.PAYMENTS_REFUND,
        Permission.PAYMENTS_SUSPEND,
        Permission.SUBSCRIPTIONS_SUSPEND, Permission.SUBSCRIPTIONS_REVOKE,
        Permission.EMAIL_READ, Permission.EMAIL_SEND,
        Permission.TELEGRAM_SEND,
        Permission.SYSTEM_SETTINGS,
        # NOTE: tickets.ban is OWNER-only (owner role = {"*"} above) — the
        # map must never grant TICKETS_BAN to staff. Admin keeps read/update/assign.
        Permission.TICKETS_READ, Permission.TICKETS_UPDATE, Permission.TICKETS_ASSIGN,
    },
    "support": {
        Permission.CLIENTS_READ,
        Permission.ACCOUNTS_READ,
        # TRADES_READ intentionally absent — trading surfaces are owner-only.
        Permission.HEALTH_READ,
        Permission.SUPPORT_READ, Permission.SUPPORT_REPLY,
        Permission.TICKETS_READ, Permission.TICKETS_UPDATE,
    },
    "risk_manager": {
        Permission.CLIENTS_READ,
        Permission.ACCOUNTS_READ, Permission.ACCOUNTS_UPDATE,
        Permission.TRADES_READ,
        Permission.ANALYTICS_READ,
        Permission.HEALTH_READ,
    },
    "analyst": {
        Permission.TRADES_READ,
        Permission.ANALYTICS_READ,
        Permission.ACCOUNTS_READ,
    },
    "billing": {
        Permission.BILLING_READ, Permission.BILLING_CREATE, Permission.BILLING_REFUND,
        Permission.PAYMENTS_READ, Permission.PAYMENTS_VERIFY, Permission.PAYMENTS_SUSPEND,
        Permission.SUBSCRIPTIONS_READ, Permission.SUBSCRIPTIONS_UPDATE,
        Permission.SUBSCRIPTIONS_SUSPEND,
        Permission.COUPONS_READ, Permission.COUPONS_CREATE,
        Permission.COUPONS_UPDATE,
        Permission.CLIENTS_READ,
    },
    "notification_mgr": {
        Permission.EMAIL_READ, Permission.EMAIL_SEND,
        Permission.TELEGRAM_SEND,
        Permission.CLIENTS_READ,
    },
    "client": {
        Permission.SELF_READ, Permission.SELF_UPDATE,
        # NO global permissions: TRADES_READ / SUBSCRIPTIONS_READ were removed
        # so clients can never reach /api/admin/* global endpoints.
        Permission.SUPPORT_READ, Permission.SUPPORT_CREATE,
    },
}


# ---------------------------------------------------------------------------
# Role hierarchy (higher number = more power)
# A user can only manage roles with a LOWER level than their own.
# ---------------------------------------------------------------------------
ROLE_HIERARCHY: dict[str, int] = {
    "owner": 100,
    "admin": 80,
    "support": 60,
    "risk_manager": 60,
    "analyst": 40,
    "billing": 40,
    "notification_mgr": 40,
    "client": 10,
}

def get_hierarchy_level(role_name: str | None) -> int:
    return ROLE_HIERARCHY.get(role_name or "client", 0)


# ---------------------------------------------------------------------------
# has_permission  (checks DB first, falls back to ROLE_PERMISSIONS)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# get_user_permissions  (returns flat list of permission strings for a user)
# ---------------------------------------------------------------------------
async def get_user_permissions(
    session: AsyncSession,
    user: User,
) -> list[str]:
    if not user.role_rel:
        return []
    role_name = user.role_rel.name
    if role_name == "owner":
        return ["*"]

    result = await session.execute(
        select(RolePermission).where(RolePermission.role_id == user.role_id).limit(1)
    )
    has_any_db_perms = result.scalar_one_or_none() is not None

    if has_any_db_perms:
        rows = await session.execute(
            select(PermissionModel.resource, PermissionModel.action)
            .join(RolePermission, RolePermission.permission_id == PermissionModel.id)
            .where(RolePermission.role_id == user.role_id)
        )
        return [f"{r.resource}.{r.action}" for r in rows.all()]

    fallback = ROLE_PERMISSIONS.get(role_name, set())
    if role_name == "owner":
        return list(fallback)
    return [p for p in fallback if p != "*"]


async def has_permission(
    session: AsyncSession,
    user: User,
    permission: str | Permission,
) -> bool:
    perm_str = permission.value if isinstance(permission, Permission) else permission

    if not user.role_rel:
        return False

    role_name = user.role_rel.name
    if role_name == "owner":
        return True

    where_clauses = [
        RolePermission.role_id == user.role_id,
    ]
    if "." in perm_str:
        # Match the seeder's split(".", 1) so three-part permissions such as
        # "system.health.read" resolve to resource="system", action="health.read".
        resource, action = perm_str.split(".", 1)
        where_clauses.append(PermissionModel.resource == resource)
        where_clauses.append(PermissionModel.action == action)
    else:
        where_clauses.append(PermissionModel.action == perm_str)

    result = await session.execute(
        select(PermissionModel)
        .join(RolePermission, RolePermission.permission_id == PermissionModel.id)
        .where(*where_clauses)
    )
    if result.scalar_one_or_none() is not None:
        return True

    # Check if role has ANY permissions in DB at all
    result = await session.execute(
        select(RolePermission).where(RolePermission.role_id == user.role_id).limit(1)
    )
    has_any_db_perms = result.scalar_one_or_none() is not None

    if has_any_db_perms:
        return False

    fallback = ROLE_PERMISSIONS.get(role_name, set())
    return perm_str in fallback


# ---------------------------------------------------------------------------
# Seed  (sync code-level ROLE_PERMISSIONS with database)
# ---------------------------------------------------------------------------
async def seed_roles_and_permissions(session: AsyncSession) -> None:
    permission_cache: dict[str, PermissionModel] = {}

    for role_name, perms in ROLE_PERMISSIONS.items():
        if perms == {"*"}:
            continue
        for perm_str in perms:
            if perm_str not in permission_cache:
                resource, action = perm_str.split(".", 1)
                result = await session.execute(
                    select(PermissionModel).where(
                        PermissionModel.resource == resource,
                        PermissionModel.action == action,
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    permission_cache[perm_str] = existing
                else:
                    p = PermissionModel(resource=resource, action=action, description=perm_str)
                    session.add(p)
                    permission_cache[perm_str] = p

    await session.flush()

    for role_name, perms in ROLE_PERMISSIONS.items():
        result = await session.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if role:
            role.description = f"Built-in {role_name} role"
        else:
            role = Role(name=role_name, description=f"Built-in {role_name} role", is_system=True)
            session.add(role)
            await session.flush()

        if perms == {"*"}:
            continue

        result = await session.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        )
        existing_rps = result.scalars().all()
        existing_perm_ids = {rp.permission_id for rp in existing_rps}

        desired_perm_ids = set()
        for perm_str in perms:
            p = permission_cache.get(perm_str)
            if p:
                desired_perm_ids.add(p.id)

        for pid in desired_perm_ids - existing_perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))

    await session.commit()
    logger.info("Roles and permissions seeded successfully")
