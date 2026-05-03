"""location visibility (Phase 6)

Revision ID: f5a6b7c8d9e0
Revises: ee96febefdb2
Create Date: 2026-05-03 12:00:00.000000

Adds `User.location_visibility` (3-tier: hidden / city_only / proximity_visible)
that backs the Phase 6 Find Brothers feature. Backfills 'hidden' for legacy
users with show_on_map=False so opt-out semantics are preserved across
the rename.
"""
from alembic import op
import sqlalchemy as sa


revision = 'f5a6b7c8d9e0'
# Chain after the merge migration that collapsed phase 3+4+5 heads.
down_revision = 'ee96febefdb2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'location_visibility',
            sa.String(length=20),
            nullable=False,
            server_default='city_only',
        ))
    # Legacy users with show_on_map=False become 'hidden'. Handles SQLite
    # boolean-as-int (0) and Postgres boolean (false) in the same UPDATE.
    op.execute(
        "UPDATE \"user\" SET location_visibility = 'hidden' "
        "WHERE show_on_map = 0 OR show_on_map = false"
    )


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('location_visibility')
