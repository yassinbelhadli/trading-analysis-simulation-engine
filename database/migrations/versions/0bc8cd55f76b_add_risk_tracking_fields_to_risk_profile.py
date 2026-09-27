"""add_risk_tracking_fields_to_risk_profile

Revision ID: 0bc8cd55f76b
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 01:39:30.255241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bc8cd55f76b'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('risk_profiles', sa.Column('initial_balance', sa.Float(), nullable=True))
    op.add_column('risk_profiles', sa.Column('day_start_balance', sa.Float(), nullable=True))
    op.add_column('risk_profiles', sa.Column('day_start_equity', sa.Float(), nullable=True))
    op.add_column('risk_profiles', sa.Column('daily_high_equity', sa.Float(), nullable=True))
    op.add_column('risk_profiles', sa.Column('drawdown_type', sa.String(length=20), nullable=True))
    op.execute("UPDATE risk_profiles SET drawdown_type = 'static' WHERE drawdown_type IS NULL")
    op.alter_column('risk_profiles', 'drawdown_type', nullable=False)
    op.add_column('risk_profiles', sa.Column('last_risk_update', sa.DateTime(timezone=True), nullable=True))
    op.add_column('risk_profiles', sa.Column('current_daily_loss_pct', sa.Float(), nullable=True))
    op.add_column('risk_profiles', sa.Column('current_max_loss_pct', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('risk_profiles', 'current_max_loss_pct')
    op.drop_column('risk_profiles', 'current_daily_loss_pct')
    op.drop_column('risk_profiles', 'last_risk_update')
    op.drop_column('risk_profiles', 'drawdown_type')
    op.drop_column('risk_profiles', 'daily_high_equity')
    op.drop_column('risk_profiles', 'day_start_equity')
    op.drop_column('risk_profiles', 'day_start_balance')
    op.drop_column('risk_profiles', 'initial_balance')
