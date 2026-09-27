"""add_name_column_to_trading_account

Revision ID: a1b2c3d4e5f6
Revises: 5599d4f834a7
Create Date: 2026-07-13 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5599d4f834a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trading_accounts', sa.Column('name', sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column('trading_accounts', 'name')
