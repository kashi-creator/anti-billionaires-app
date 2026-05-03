#!/usr/bin/env python3
"""Invite an admin to Sovereign Society.

Usage:
    python scripts/invite_admin.py <email> "<full name>"
    railway run python scripts/invite_admin.py <email> "<full name>"   # against prod

Idempotent: if the user already exists, promotes them to admin and refreshes
the password-reset token. If they don't, creates the account with a random
temp password (immediately superseded by the reset flow).

Always:
- is_admin=True
- lifetime_access=True (no paywall, no Stripe interaction)
- subscription_status="active"
- email_verified=True
- 7-day password-reset token

Prints the reset link to stdout AND attempts to send a password-reset email.
The link works regardless of email delivery — DM it to the invitee as a fallback.
"""

import sys
import os
import secrets
from datetime import datetime, timedelta, date

# Make repo root importable when run as `python scripts/invite_admin.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt

from app import app
from models import db, User
from email_send import send_password_reset


def invite_admin(email: str, name: str) -> None:
    email = email.lower().strip()
    with app.app_context():
        user = User.query.filter_by(email=email).first()

        if user:
            user.is_admin = True
            user.lifetime_access = True
            user.subscription_status = "active"
            user.email_verified = True
            if not user.lifetime_qualified_at:
                user.lifetime_qualified_at = datetime.utcnow()
            user.password_reset_token = secrets.token_urlsafe(32)
            user.password_reset_expires = datetime.utcnow() + timedelta(days=7)
            user.ensure_referral_code()
            db.session.commit()
            print(f"Promoted existing user {user.id} ({email}) to admin")
        else:
            temp_password = secrets.token_urlsafe(32)
            hashed = bcrypt.hashpw(temp_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user = User(
                email=email,
                name=name,
                password_hash=hashed,
                is_admin=True,
                lifetime_access=True,
                subscription_status="active",
                email_verified=True,
                lifetime_qualified_at=datetime.utcnow(),
                password_reset_token=secrets.token_urlsafe(32),
                password_reset_expires=datetime.utcnow() + timedelta(days=7),
                points=0,
                streak_days=1,
                last_login_date=date.today(),
            )
            user.ensure_referral_code()
            db.session.add(user)
            db.session.commit()
            print(f"Created admin user {user.id} ({email})")

        host = "https://anti-billionaires-app-production.up.railway.app"
        reset_link = f"{host}/reset-password/{user.password_reset_token}"
        print(f"Reset link (valid 7 days): {reset_link}")

        try:
            send_password_reset(user, reset_link)
            print("Password-reset email dispatched")
        except Exception as e:
            print(f"WARN: send_password_reset failed: {e}")
            print("DM the reset link above to the invitee instead.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Usage: python scripts/invite_admin.py <email> "<full name>"')
        sys.exit(1)
    invite_admin(sys.argv[1], sys.argv[2])
