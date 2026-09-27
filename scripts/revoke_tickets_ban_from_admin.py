"""Fix: revoke stale tickets.ban from the DB admin role + revert QA-ban side effects.

Why: seed_roles_and_permissions() is add-only (never deletes RolePermission rows),
so removing TICKETS_BAN from ROLE_PERMISSIONS['admin'] did NOT clear the DB link —
require_permission consults the DB first when the role has any linked permissions,
so admin could still call POST /api/admin/tickets/{id}/ban (owner-only).

Also reverts the licenses suspended by the QA ban on demo.client (ticket service
only suspends licenses + closes the ticket; user row is untouched).

Idempotent: safe to re-run.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from database.db import async_session_factory

DEMO_CLIENT_ID = "4f14e067-5904-5dc4-a290-b3de5e126f30"  # demo.client@ict-ea-demo.dev


async def main() -> None:
    async with async_session_factory() as s:
        # 1) Remove admin -> tickets.ban link (permission resource='tickets', action='ban')
        r = await s.execute(
            text(
                "delete from role_permissions rp "
                "using permissions p, roles ro "
                "where rp.permission_id = p.id and rp.role_id = ro.id "
                "and ro.name = 'admin' and p.resource = 'tickets' and p.action = 'ban'"
            )
        )
        print(f"admin tickets.ban links removed: {r.rowcount}")

        # 2) Revert demo.client licenses suspended by the QA ban
        r = await s.execute(
            text(
                "update licenses set status = 'active' "
                "where user_id = :uid and status = 'suspended'"
            ),
            {"uid": DEMO_CLIENT_ID},
        )
        print(f"demo.client licenses reactivated: {r.rowcount}")

        # 3) Verify no stale tickets.ban remains for any staff role
        rows = await s.execute(
            text(
                "select ro.name from role_permissions rp "
                "join permissions p on p.id = rp.permission_id "
                "join roles ro on ro.id = rp.role_id "
                "where p.resource = 'tickets' and p.action = 'ban'"
            )
        )
        holders = [row[0] for row in rows]
        print(f"roles still holding tickets.ban: {holders or 'NONE'}")

        await s.commit()


asyncio.run(main())
