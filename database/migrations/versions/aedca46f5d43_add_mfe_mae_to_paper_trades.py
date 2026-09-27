"""add_mfe_mae_to_paper_trades

Revision ID: aedca46f5d43
Revises: 78854bdef4cc
Create Date: 2026-07-19 19:20:13.281225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aedca46f5d43'
down_revision: Union[str, Sequence[str], None] = '78854bdef4cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('paper_trades', sa.Column('highest_price', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('lowest_price', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('mfe', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('mae', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('paper_trades', 'mae')
    op.drop_column('paper_trades', 'mfe')
    op.drop_column('paper_trades', 'lowest_price')
    op.drop_column('paper_trades', 'highest_price')
