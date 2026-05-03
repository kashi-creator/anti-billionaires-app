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
    # Direct op.add_column avoids batch_alter_table reflection on the user
    # table, which trips a CircularDependencyError in this alembic /
    # sqlalchemy version when sorting columns near the recently-stacked
    # last_engagement_email_at / last_digest_sent_at / assessment_complete
    # additions. Postgres and SQLite both support ADD COLUMN with NOT NULL +
    # server_default natively.
    op.add_column('user', sa.Column(
        'location_visibility',
        sa.String(length=20),
        nullable=False,
        server_default='city_only',
    ))
    # Legacy users with show_on_map=False become 'hidden'. Postgres rejects
    # boolean-vs-int comparisons; use the boolean form which sqlite also accepts.
    op.execute(
        "UPDATE \"user\" SET location_visibility = 'hidden' WHERE show_on_map IS FALSE"
    )


def downgrade():
    op.drop_column('user', 'location_visibility')
