"""push subscriptions for web push (PWA)

Revision ID: a7b8c9d0e1f2
Revises: c1d2e3f4a5b6
Create Date: 2026-05-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'push_subscription',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('endpoint', sa.String(length=700), nullable=False),
        sa.Column('p256dh', sa.String(length=200), nullable=False),
        sa.Column('auth', sa.String(length=64), nullable=False),
        sa.Column('user_agent', sa.String(length=300), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_push_subscription_user_id', 'push_subscription', ['user_id'])
    op.create_unique_constraint('uq_push_subscription_endpoint', 'push_subscription', ['endpoint'])


def downgrade():
    op.drop_constraint('uq_push_subscription_endpoint', 'push_subscription', type_='unique')
    op.drop_index('ix_push_subscription_user_id', table_name='push_subscription')
    op.drop_table('push_subscription')
