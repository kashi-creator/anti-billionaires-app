"""device tokens for push notifications

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-04-30 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd3e4f5a6b7c8'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'device_token',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_device_token_user_id', 'device_token', ['user_id'])
    op.create_unique_constraint('uq_device_token_token', 'device_token', ['token'])


def downgrade():
    op.drop_constraint('uq_device_token_token', 'device_token', type_='unique')
    op.drop_index('ix_device_token_user_id', table_name='device_token')
    op.drop_table('device_token')
