"""user.install_acknowledged_at — PWA install hard-step gate

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-06 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('install_acknowledged_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('user', 'install_acknowledged_at')
