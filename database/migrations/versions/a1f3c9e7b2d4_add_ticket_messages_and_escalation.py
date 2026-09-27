"""add_ticket_messages_and_escalation

Adds the conversation model for the unified support/ticket system:

- ``ticket_messages`` table (client messages + internal staff notes)
- escalation metadata columns (escalated_at, escalation_target, escalation_reason)
- assignment columns (assignee_id, assigned_at)
- resolved_at + source columns
- ``support_ticket_seq`` sequence for concurrency-safe ticket numbering

Revision ID: a1f3c9e7b2d4
Revises: 031564ef4e71
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f3c9e7b2d4'
down_revision: Union[str, Sequence[str], None] = '031564ef4e71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- support_tickets: escalation / assignment / resolution metadata ---
    op.add_column('support_tickets', sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('support_tickets', sa.Column('escalation_target', sa.String(length=20), nullable=True))
    op.add_column('support_tickets', sa.Column('escalation_reason', sa.Text(), nullable=True))
    op.add_column('support_tickets', sa.Column('assignee_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('support_tickets', sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('support_tickets', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('support_tickets', sa.Column('source', sa.String(length=20), nullable=False, server_default='dashboard'))
    op.create_index('ix_support_tickets_assignee_id', 'support_tickets', ['assignee_id'])

    # --- ticket_messages: shared conversation across all surfaces ---
    op.create_table(
        'ticket_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('ticket_id', sa.String(length=36), sa.ForeignKey('support_tickets.id'), nullable=False),
        sa.Column('author_user_id', sa.String(length=36), nullable=True),
        sa.Column('author_role', sa.String(length=20), nullable=False, server_default='client'),
        sa.Column('author_name', sa.String(length=100), nullable=True),
        sa.Column('kind', sa.String(length=10), nullable=False, server_default='message'),
        sa.Column('is_internal', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ticket_messages_ticket_id', 'ticket_messages', ['ticket_id'])
    op.create_index('ix_ticket_messages_created_at', 'ticket_messages', ['created_at'])

    # --- concurrency-safe ticket numbering ---
    # Sequence start is seeded past any existing TKT-* number so fresh tickets
    # can never collide with legacy COUNT+1 numbers (unique constraint).
    # Postgres setval() rejects 0, so the fallback is 1 (nextval -> 2).
    op.execute("CREATE SEQUENCE IF NOT EXISTS support_ticket_seq")
    op.execute(
        "SELECT setval('support_ticket_seq', GREATEST(COALESCE(("
        "SELECT MAX(CAST(SUBSTRING(ticket_number FROM 5) AS INTEGER)) "
        "FROM support_tickets WHERE ticket_number ~ '^TKT-[0-9]+$'), 1), 1))"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP SEQUENCE IF EXISTS support_ticket_seq")
    op.drop_index('ix_ticket_messages_created_at', table_name='ticket_messages')
    op.drop_index('ix_ticket_messages_ticket_id', table_name='ticket_messages')
    op.drop_table('ticket_messages')
    op.drop_index('ix_support_tickets_assignee_id', table_name='support_tickets')
    op.drop_column('support_tickets', 'source')
    op.drop_column('support_tickets', 'resolved_at')
    op.drop_column('support_tickets', 'assigned_at')
    op.drop_column('support_tickets', 'assignee_id')
    op.drop_column('support_tickets', 'escalation_reason')
    op.drop_column('support_tickets', 'escalation_target')
    op.drop_column('support_tickets', 'escalated_at')
