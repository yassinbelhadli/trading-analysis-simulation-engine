"""add_realized_r_and_risk_amount

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-07-20 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('paper_trades', sa.Column('realized_r', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('initial_risk_usd', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('paper_trades', 'realized_r')
    op.drop_column('paper_trades', 'initial_risk_usd')
