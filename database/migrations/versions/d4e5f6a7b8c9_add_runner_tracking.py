"""add_runner_tracking

Revision ID: d4e5f6a7b8c9
Revises: f69e3c8a1d2b
Create Date: 2026-07-20 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'f69e3c8a1d2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('paper_trades', sa.Column('post_partial_highest_price', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('post_partial_lowest_price', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('runner_mfe', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('runner_efficiency', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('paper_trades', 'runner_efficiency')
    op.drop_column('paper_trades', 'runner_mfe')
    op.drop_column('paper_trades', 'post_partial_lowest_price')
    op.drop_column('paper_trades', 'post_partial_highest_price')
