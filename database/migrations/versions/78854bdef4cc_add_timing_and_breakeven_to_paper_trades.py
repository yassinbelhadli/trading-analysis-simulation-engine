"""add_timing_and_breakeven_to_paper_trades

Revision ID: 78854bdef4cc
Revises: 0bc8cd55f76b
Create Date: 2026-07-19 18:31:29.350784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78854bdef4cc'
down_revision: Union[str, Sequence[str], None] = '0bc8cd55f76b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('paper_trades', sa.Column('fill_latency_sec', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('trade_duration_sec', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('breakeven_activated', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('paper_trades', sa.Column('breakeven_price', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('paper_trades', 'breakeven_price')
    op.drop_column('paper_trades', 'breakeven_activated')
    op.drop_column('paper_trades', 'trade_duration_sec')
    op.drop_column('paper_trades', 'fill_latency_sec')
