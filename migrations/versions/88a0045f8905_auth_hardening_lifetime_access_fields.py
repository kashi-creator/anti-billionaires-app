"""auth hardening + lifetime access fields

Revision ID: 88a0045f8905
Revises: 43be3a8d6b40
Create Date: 2026-04-30 21:59:14.067761

"""
from alembic import op
import sqlalchemy as sa


revision = '88a0045f8905'
down_revision = '43be3a8d6b40'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('email_verify_token', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('email_verify_expires', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('password_reset_token', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('password_reset_expires', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('payments_made_count', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('lifetime_access', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('onboarding_complete', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.create_index('ix_user_email_verify_token', ['email_verify_token'], unique=False)
        batch_op.create_index('ix_user_password_reset_token', ['password_reset_token'], unique=False)
        batch_op.create_unique_constraint('uq_user_referral_code', ['referral_code'])
        batch_op.create_foreign_key('fk_user_referred_by', 'user', ['referred_by'], ['id'])


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_referred_by', type_='foreignkey')
        batch_op.drop_constraint('uq_user_referral_code', type_='unique')
        batch_op.drop_index('ix_user_password_reset_token')
        batch_op.drop_index('ix_user_email_verify_token')
        batch_op.drop_column('onboarding_complete')
        batch_op.drop_column('lifetime_access')
        batch_op.drop_column('payments_made_count')
        batch_op.drop_column('password_reset_expires')
        batch_op.drop_column('password_reset_token')
        batch_op.drop_column('email_verify_expires')
        batch_op.drop_column('email_verify_token')
        batch_op.drop_column('email_verified')
