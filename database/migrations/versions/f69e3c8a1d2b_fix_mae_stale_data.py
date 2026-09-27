"""fix_mae_stale_data

Revision ID: f69e3c8a1d2b
Revises: b01432654b54
Create Date: 2026-07-20 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f69e3c8a1d2b'
down_revision: Union[str, Sequence[str], None] = 'b01432654b54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE paper_trades SET mae = 0.0 WHERE mae < 0")
    op.execute("UPDATE paper_trades SET mfe = 0.0 WHERE mfe < 0")
    op.execute(
        "UPDATE paper_trades "
        "SET close_reason = 'STALE_CLEANUP' "
        "WHERE status = 'CLOSED' AND close_reason IS NULL"
    )


def downgrade() -> None:
    pass
