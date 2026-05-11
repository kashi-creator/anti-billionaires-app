"""team_post_queue: scheduled team posts

Revision ID: 9926b13b9552
Revises: c9d1f3a8b6e2
Create Date: 2026-05-11 12:05:20.569676

Phase 14. New table for the Sovereign Society Team post queue. The
`Sovereign Society Team` user (prod id=11, email team@sovereignsociety.rich)
publishes one row per Space every TEAM_POST_CADENCE_DAYS days via the
`flask cron team-post-publish` command. Status vocab locked
(pending|published|skipped) — enforced via @validates on the model.
Indexes on space_id + status for cron lookup. published_post_id is
nullable, populated only on publish.

Postgres-vs-SQLite note: use `server_default=sa.text("'pending'")` for
the string default (NOT `'pending'` plain — alembic on postgres needs
the SQL literal). queue_position uses an integer literal default of 0.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9926b13b9552'
down_revision = 'c9d1f3a8b6e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'team_post_queue',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('space_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('queue_position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('published_post_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['space_id'], ['space.id'], name='fk_team_post_queue_space_id'),
        sa.ForeignKeyConstraint(['published_post_id'], ['post.id'], name='fk_team_post_queue_published_post_id'),
    )
    op.create_index('ix_team_post_queue_space_id', 'team_post_queue', ['space_id'])
    op.create_index('ix_team_post_queue_status', 'team_post_queue', ['status'])


def downgrade():
    op.drop_index('ix_team_post_queue_status', table_name='team_post_queue')
    op.drop_index('ix_team_post_queue_space_id', table_name='team_post_queue')
    op.drop_table('team_post_queue')
