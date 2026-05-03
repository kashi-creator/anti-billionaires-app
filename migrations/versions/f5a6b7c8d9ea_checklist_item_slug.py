"""checklist_item.slug

Revision ID: f5a6b7c8d9ea
Revises: e4f5a6b7c8d9
Create Date: 2026-05-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f5a6b7c8d9ea'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('checklist_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('slug', sa.String(length=60), nullable=True))
        batch_op.create_unique_constraint('uq_checklist_item_slug', ['slug'])


def downgrade():
    with op.batch_alter_table('checklist_item', schema=None) as batch_op:
        batch_op.drop_constraint('uq_checklist_item_slug', type_='unique')
        batch_op.drop_column('slug')
