"""engagement email throttling

Revision ID: abcd1234e5f6
Revises: 9c1f2a3e4d5b
Create Date: 2026-04-30 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'abcd1234e5f6'
down_revision = '9c1f2a3e4d5b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_engagement_email_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_digest_sent_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('last_digest_sent_at')
        batch_op.drop_column('last_engagement_email_at')
