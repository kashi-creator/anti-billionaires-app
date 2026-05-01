"""hot-path indexes for perf

Revision ID: c2d3e4f5a6b7
Revises: abcd1234e5f6
Create Date: 2026-04-30 23:30:00.000000

"""
from alembic import op


revision = 'c2d3e4f5a6b7'
down_revision = 'abcd1234e5f6'
branch_labels = None
depends_on = None


INDEXES = [
    ('ix_post_user_id', 'post', ['user_id']),
    ('ix_post_space_id', 'post', ['space_id']),
    ('ix_post_created_at', 'post', ['created_at']),
    ('ix_comment_post_id', 'comment', ['post_id']),
    ('ix_like_post_id', 'like', ['post_id']),
    ('ix_like_user_id', 'like', ['user_id']),
    ('ix_notification_user_id', 'notification', ['user_id']),
    ('ix_notification_is_read', 'notification', ['is_read']),
    ('ix_conversation_user1', 'conversation', ['user1_id']),
    ('ix_conversation_user2', 'conversation', ['user2_id']),
    ('ix_message_conversation', 'message', ['conversation_id']),
    ('ix_message_is_read', 'message', ['is_read']),
    ('ix_win_created_at', 'win', ['created_at']),
    ('ix_space_membership_user', 'space_membership', ['user_id']),
    ('ix_space_membership_space', 'space_membership', ['space_id']),
    ('ix_user_subscription_status', 'user', ['subscription_status']),
    ('ix_user_lifetime_access', 'user', ['lifetime_access']),
    ('ix_aichat_user_id', 'ai_chat', ['user_id']),
    ('ix_aichat_created_at', 'ai_chat', ['created_at']),
    ('ix_activity_user_id', 'activity', ['user_id']),
    ('ix_bookmark_user_id', 'bookmark', ['user_id']),
    ('ix_follow_follower', 'follow', ['follower_id']),
    ('ix_follow_followed', 'follow', ['followed_id']),
]


def upgrade():
    for name, table, cols in INDEXES:
        try:
            op.create_index(name, table, cols)
        except Exception as e:
            print(f"[migration] skipping index {name}: {e}")


def downgrade():
    for name, table, _ in INDEXES:
        try:
            op.drop_index(name, table_name=table)
        except Exception:
            pass
