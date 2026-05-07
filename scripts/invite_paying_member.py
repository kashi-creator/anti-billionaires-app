#!/usr/bin/env python3
"""Invite a paying member who's billed through a channel outside SS Stripe.

These members get:
- User row with subscription_status="active" (paywall passes immediately)
- lifetime_access=False (they earn lifetime the normal way via 3 referrals × 6 paid)
- email_verified=True (skip verification — they paid us; they exist)
- 7-day password-reset token + reset email so they set their own password
- GHL contact with stage_tag="active-member" + "external-billing" extra tag

Usage:
    railway run sh -c "DATABASE_URL='$PUBLIC_DB' .venv/bin/python \\
      scripts/invite_paying_member.py <email> '<full name>' \\
      [--phone PHONE] [--company COMPANY]"

The "external-billing" tag lets GHL workflows distinguish these members from
in-app-Stripe payers, since their future payments don't fire SS webhooks.
If their external billing lapses, an admin must manually flip
subscription_status to inactive via /admin (no automated downgrade for them).
"""

import sys
import os
import secrets
import argparse
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from app import app
from models import db, User
from email_send import send_password_reset
from lib import ghl


def invite_paying_member(email, name, phone=None, company=None):
    email = email.lower().strip()
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user:
            user.subscription_status = "active"
            user.email_verified = True
            user.password_reset_token = secrets.token_urlsafe(32)
            user.password_reset_expires = datetime.utcnow() + timedelta(days=7)
            user.ensure_referral_code()
            db.session.commit()
            print(f"Promoted existing user {user.id} ({email}) to active paying member")
        else:
            temp_password = secrets.token_urlsafe(32)
            hashed = bcrypt.hashpw(temp_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            bio = f"Owner of {company}." if company else ""
            user = User(
                email=email,
                name=name,
                password_hash=hashed,
                bio=bio,
                subscription_status="active",
                email_verified=True,
                payments_made_count=0,
                lifetime_access=False,
                last_login_date=date.today(),
                points=0,
                streak_days=1,
                password_reset_token=secrets.token_urlsafe(32),
                password_reset_expires=datetime.utcnow() + timedelta(days=7),
            )
            user.ensure_referral_code()
            db.session.add(user)
            db.session.commit()
            print(f"Created paying member user {user.id} ({email})")

        custom_fields = ghl.custom_fields_from_user(user)
        if company:
            custom_fields["company"] = company

        ghl.upsert_contact(
            email=email,
            name=name,
            phone=phone,
            stage_tag="active-member",
            custom_fields=custom_fields,
            extra_tags=["external-billing"],
        )
        print(f"GHL contact upserted: {email} stage_tag=active-member +external-billing")
        if company:
            print(f"  company custom field: {company}")
        if phone:
            print(f"  phone: {phone}")

        host = "https://" + os.environ.get(
            "SERVER_NAME", "anti-billionaires-app-production.up.railway.app"
        )
        reset_link = f"{host}/reset-password/{user.password_reset_token}"
        print(f"Reset link (valid 7 days): {reset_link}")

        try:
            sent = send_password_reset(user, reset_link, async_=False)
            print(f"Password-reset email send result: {sent}")
            if not sent:
                print(f"DM the reset link above to {email}")
        except Exception as e:
            print(f"WARN: send_password_reset failed: {e}")
            print(f"DM the reset link above to {email}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("email")
    p.add_argument("name")
    p.add_argument("--phone")
    p.add_argument("--company")
    args = p.parse_args()
    invite_paying_member(args.email, args.name, phone=args.phone, company=args.company)
