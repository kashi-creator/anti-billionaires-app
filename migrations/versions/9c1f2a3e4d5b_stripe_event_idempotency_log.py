"""stripe event idempotency log

Revision ID: 9c1f2a3e4d5b
Revises: 88a0045f8905
Create Date: 2026-04-30 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9c1f2a3e4d5b'
down_revision = '88a0045f8905'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'stripe_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('stripe_event_id', sa.String(length=80), nullable=False),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint('uq_stripe_event_id', 'stripe_event', ['stripe_event_id'])
    op.create_index('ix_stripe_event_id', 'stripe_event', ['stripe_event_id'])


def downgrade():
    op.drop_index('ix_stripe_event_id', table_name='stripe_event')
    op.drop_constraint('uq_stripe_event_id', 'stripe_event', type_='unique')
    op.drop_table('stripe_event')
