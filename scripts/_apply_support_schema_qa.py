"""Apply the support-tickets migration DDL to the QA DB (create_all-managed env).

QA databases are built with Base.metadata.create_all and are not tracked by
Alembic, so we apply the equivalent DDL idempotently. The Alembic revision
a1f3c9e7b2d4 remains the source of truth for migration-managed environments.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa",
)

import sqlalchemy as sa
from database.db import engine

DDL = [
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMPTZ",
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS escalation_target VARCHAR(20)",
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS escalation_reason TEXT",
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS assignee_id VARCHAR(36) REFERENCES users(id)",
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ",
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ",
    "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'dashboard'",
    "CREATE TABLE IF NOT EXISTS ticket_messages ("
    " id VARCHAR(36) NOT NULL PRIMARY KEY,"
    " ticket_id VARCHAR(36) NOT NULL REFERENCES support_tickets(id),"
    " author_user_id VARCHAR(36),"
    " author_role VARCHAR(20) NOT NULL DEFAULT 'client',"
    " author_name VARCHAR(100),"
    " kind VARCHAR(10) NOT NULL DEFAULT 'message',"
    " is_internal BOOLEAN NOT NULL DEFAULT FALSE,"
    " body TEXT NOT NULL,"
    " created_at TIMESTAMPTZ NOT NULL"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_ticket_messages_ticket_id ON ticket_messages(ticket_id)",
    "CREATE INDEX IF NOT EXISTS ix_ticket_messages_created_at ON ticket_messages(created_at)",
    "CREATE INDEX IF NOT EXISTS ix_support_tickets_assignee_id ON support_tickets(assignee_id)",
    "CREATE SEQUENCE IF NOT EXISTS support_ticket_seq",
]


async def main():
    async with engine.begin() as c:
        for stmt in DDL:
            await c.execute(sa.text(stmt))
        # Seed sequence past any existing TKT-* numbers (mirror of migration).
        # setval() rejects 0, so the fallback is 1 (nextval -> 2).
        await c.execute(
            sa.text(
                "SELECT setval('support_ticket_seq', GREATEST(COALESCE(("
                "SELECT MAX(CAST(SUBSTRING(ticket_number FROM 5) AS INTEGER)) "
                "FROM support_tickets WHERE ticket_number ~ '^TKT-[0-9]+$'), 1), 1))"
            )
        )
    print("QA support schema OK")


asyncio.run(main())
