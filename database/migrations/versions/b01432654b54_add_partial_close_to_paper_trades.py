"""add_partial_close_to_paper_trades

Revision ID: b01432654b54
Revises: aedca46f5d43
Create Date: 2026-07-20 00:00:29.355028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b01432654b54'
down_revision: Union[str, Sequence[str], None] = 'aedca46f5d43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('paper_trades', sa.Column('partial_closed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('paper_trades', sa.Column('partial_price', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('partial_pnl', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('paper_trades', 'partial_pnl')
    op.drop_column('paper_trades', 'partial_price')
    op.drop_column('paper_trades', 'partial_closed')
