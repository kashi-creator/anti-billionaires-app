"""referral qualification fields

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-04-30 23:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('qualified_referrals_count', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('lifetime_qualified_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('lifetime_qualified_at')
        batch_op.drop_column('qualified_referrals_count')
