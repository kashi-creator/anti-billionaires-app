"""events: add type/chapter/recurrence fields

Revision ID: b1e2f5a6c7d8
Revises: e4f5a6b7c8d9
Create Date: 2026-05-03 00:00:00.000000

Adds the four new columns + self-FK that let an Event row act as a
recurrence template (`is_recurrence_template=True`, `recurrence_rule != "none"`)
and produce per-occurrence child rows (each with `recurrence_parent_id` set
to the template's id and `recurrence_rule="none"`). See INTEGRATION-SOURCE-OF-TRUTH.md
§9 for the locked vocabulary on event_type / recurrence_rule.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b1e2f5a6c7d8'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'event_type', sa.String(length=40), nullable=False,
            server_default=sa.text("'official_one_off'"),
        ))
        batch_op.add_column(sa.Column('chapter', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column(
            'recurrence_rule', sa.String(length=60), nullable=False,
            server_default=sa.text("'none'"),
        ))
        batch_op.add_column(sa.Column('recurrence_parent_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column(
            'is_recurrence_template', sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ))
        batch_op.create_foreign_key(
            'fk_event_recurrence_parent_id',
            'event', ['recurrence_parent_id'], ['id'],
        )
        batch_op.create_index(
            'ix_event_recurrence_parent_id', ['recurrence_parent_id'],
        )


def downgrade():
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_index('ix_event_recurrence_parent_id')
        batch_op.drop_constraint('fk_event_recurrence_parent_id', type_='foreignkey')
        batch_op.drop_column('is_recurrence_template')
        batch_op.drop_column('recurrence_parent_id')
        batch_op.drop_column('recurrence_rule')
        batch_op.drop_column('chapter')
        batch_op.drop_column('event_type')
