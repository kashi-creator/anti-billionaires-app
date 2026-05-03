"""assessment models

Revision ID: f5a6b7c8d9ec
Revises: e4f5a6b7c8d9
Create Date: 2026-05-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f5a6b7c8d9ec'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assessment_complete', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        'assessment_response',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('answers_json', sa.Text(), nullable=False),
        sa.Column('pillar_scores_json', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    )
    op.create_index('ix_assessment_response_user_id', 'assessment_response', ['user_id'])


def downgrade():
    op.drop_index('ix_assessment_response_user_id', table_name='assessment_response')
    op.drop_table('assessment_response')
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('assessment_complete')
