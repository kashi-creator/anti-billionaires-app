"""add phone to user (for SMS reminders / GHL sync)

Revision ID: a1b2c3d4e5f6
Revises: 9926b13b9552
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9926b13b9552'
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN — supported directly by both SQLite and Postgres, so we
    # avoid batch-mode table recreation (which fails on SQLite's unnamed
    # unique constraints).
    op.add_column('user', sa.Column('phone', sa.String(length=40), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('phone')
