"""projects: project + project_update + project_interest + project_payment_method

Revision ID: c1d2e3f4a5b6
Revises: f5a6b7c8d9e0
Create Date: 2026-05-03 00:00:00.000000

Phase 7. Four new tables for member-published builds:
- project: the build itself, owned by a user, with locked vocab on
  status / project_type / visibility (enforced via @validates on the model;
  this migration only adds the columns — no DB-level CHECK constraint)
- project_update: creator-only progress notes, ordered desc by created_at
- project_interest: idempotent toggle (one row per user per project)
- project_payment_method: directory-only payment-handle list (SS does NOT
  process; off-platform). Locked method_type vocab + shape regex enforced
  via @validates on the model.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = 'f5a6b7c8d9e0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'project',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('summary', sa.String(length=500), server_default=''),
        sa.Column('description', sa.Text(), server_default=''),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='building'),
        sa.Column('project_type', sa.String(length=40), nullable=False, server_default='business'),
        sa.Column('looking_for', sa.String(length=100), server_default=''),
        sa.Column('cover_image', sa.String(length=300), nullable=True),
        sa.Column('visibility', sa.String(length=20), nullable=False, server_default='members_only'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    )
    op.create_index('ix_project_user_id', 'project', ['user_id'])

    op.create_table(
        'project_update',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('image_path', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['project.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    )
    op.create_index('ix_project_update_project_id', 'project_update', ['project_id'])

    op.create_table(
        'project_interest',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('message', sa.Text(), server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['project.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.UniqueConstraint('project_id', 'user_id', name='unique_project_interest'),
    )
    op.create_index('ix_project_interest_project_id', 'project_interest', ['project_id'])

    op.create_table(
        'project_payment_method',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('method_type', sa.String(length=40), nullable=False),
        sa.Column('address_or_handle', sa.String(length=500), nullable=False),
        sa.Column('label', sa.String(length=100), server_default=''),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['project.id']),
    )
    op.create_index('ix_project_payment_method_project_id', 'project_payment_method', ['project_id'])


def downgrade():
    op.drop_index('ix_project_payment_method_project_id', table_name='project_payment_method')
    op.drop_table('project_payment_method')
    op.drop_index('ix_project_interest_project_id', table_name='project_interest')
    op.drop_table('project_interest')
    op.drop_index('ix_project_update_project_id', table_name='project_update')
    op.drop_table('project_update')
    op.drop_index('ix_project_user_id', table_name='project')
    op.drop_table('project')
