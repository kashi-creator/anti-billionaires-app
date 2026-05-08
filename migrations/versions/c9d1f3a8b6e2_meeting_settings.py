"""meeting_settings

Revision ID: c9d1f3a8b6e2
Revises: b8c9d0e1f2a3
Create Date: 2026-05-08 18:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c9d1f3a8b6e2'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'meeting_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_date', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('meeting_time', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('meeting_location', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('meeting_settings')
