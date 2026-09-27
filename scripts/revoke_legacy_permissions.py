"""
One-time (idempotent) DB cleanup: revoke legacy permission grants that were
removed from ROLE_PERMISSIONS (security/access_control.py) in the RBAC
tightening.

Revoked (route-level require_role("owner") is the authoritative guard; this
removes the stale role_permissions rows so has_permission() reflects the
new policy for any future route):
  - admin  : trades.read, trades.export, trades.view, engine.read,
             engine.control, roles.read, roles.create, roles.update,
             roles.delete, roles.assign
  - support: trades.read
  - client : trades.read, subscriptions.read

Usage:  .venv\\Scripts\\python.exe scripts\\revoke_legacy_permissions.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from database.db import async_session_factory
from database.models import Permission as PermissionModel, Role, RolePermission

REVOKE: dict[str, list[str]] = {
    "admin": [
        "trades.read", "trades.export", "trades.view",
        "engine.read", "engine.control",
        "roles.read", "roles.create", "roles.update", "roles.delete", "roles.assign",
    ],
    "support": ["trades.read"],
    "client": ["trades.read", "subscriptions.read"],
}


async def main() -> None:
    async with async_session_factory() as session:
        for role_name, perm_strings in REVOKE.items():
            role = (
                await session.execute(select(Role).where(Role.name == role_name))
            ).scalar_one_or_none()
            if not role:
                print(f"role '{role_name}': not found — skipped")
                continue

            deleted = 0
            for perm_str in perm_strings:
                resource, action = perm_str.split(".", 1)
                perm = (
                    await session.execute(
                        select(PermissionModel).where(
                            PermissionModel.resource == resource,
                            PermissionModel.action == action,
                        )
                    )
                ).scalar_one_or_none()
                if not perm:
                    print(f"  permission '{perm_str}': not in DB — skipped")
                    continue
                rp = (
                    await session.execute(
                        select(RolePermission).where(
                            RolePermission.role_id == role.id,
                            RolePermission.permission_id == perm.id,
                        )
                    )
                ).scalar_one_or_none()
                if rp:
                    await session.delete(rp)
                    deleted += 1
            print(f"role '{role_name}': revoked {deleted} permission grant(s)")

        await session.commit()
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
