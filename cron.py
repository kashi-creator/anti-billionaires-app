"""Scheduled jobs and engagement email triggers.

Designed to be called from Railway Cron Jobs (or similar) via:
    flask digest         # weekly digest
    flask dm-notify <user_id> <sender_id>   # one-off DM email

Also exposes Python helpers used inline by route handlers
(e.g. notify_dm_throttled in features_routes.send_message).
"""
from datetime import datetime, timedelta
import click
from flask.cli import AppGroup

from models import db, User, Win, Activity, Event, Message, Conversation
from email_send import send_weekly_digest


cron_cli = AppGroup("cron")
DM_EMAIL_DEBOUNCE_HOURS = 1


def notify_dm_throttled(recipient: User, sender: User, preview: str):
    """Send 'you got a DM' email, but only if we haven't sent one in the last hour."""
    if recipient.email_digest_opt_out:
        return False
    now = datetime.utcnow()
    if recipient.last_engagement_email_at and (now - recipient.last_engagement_email_at) < timedelta(hours=DM_EMAIL_DEBOUNCE_HOURS):
        return False
    from email_send import send_email
    send_email(
        to=recipient.email,
        subject=f"{sender.name} sent you a message",
        body_text=f"{sender.name} sent you a DM in Sovereign Society:\n\n\"{preview[:200]}\"\n\nReply at the Society.",
    )
    recipient.last_engagement_email_at = now
    db.session.commit()
    return True


def notify_challenge_announce(challenge_title: str, challenge_id: int):
    """Email all members about a new weekly challenge."""
    from email_send import send_email
    members = User.query.filter_by(email_digest_opt_out=False).filter(
        (User.lifetime_access == True) | (User.subscription_status == "active")
    ).all()
    for u in members:
        send_email(
            to=u.email,
            subject=f"New challenge: {challenge_title}",
            body_text=f"Hi {u.name},\n\nThis week's challenge is live: {challenge_title}\n\nJump in at Sovereign Society.",
        )


def _build_digest_data(since: datetime, until: datetime):
    """Pull top wins, spotlight, and upcoming events for the digest window."""
    top_wins = (
        db.session.query(Win)
        .filter(Win.created_at >= since, Win.created_at < until)
        .order_by(Win.created_at.desc())
        .limit(5)
        .all()
    )
    top_wins_data = [
        {
            "author_name": w.author.name if w.author else "Member",
            # Win has title + description, not a single `content` column.
            "content": f"{w.title} - {w.description}" if w.description else w.title,
        }
        for w in top_wins
    ]

    spotlight = (
        User.query
        .filter((User.lifetime_access == True) | (User.subscription_status == "active"))
        .order_by(User.points.desc())
        .first()
    )

    # Event has separate `date` (Date) + `time` (str) columns — no `starts_at`.
    today = datetime.utcnow().date()
    week_out = today + timedelta(days=7)
    upcoming = (
        Event.query
        .filter(Event.date >= today, Event.date < week_out)
        .order_by(Event.date.asc())
        .limit(5)
        .all()
    )
    upcoming_data = [
        {
            "date": e.date.strftime("%a %b %d") + (f" {e.time}" if e.time else ""),
            "title": e.title,
        }
        for e in upcoming if e.date
    ]

    return {
        "top_wins": top_wins_data,
        "spotlight": spotlight,
        "upcoming_events": upcoming_data,
    }


def run_weekly_digest():
    """Send the weekly digest to every opted-in active member.
    Idempotent within a 6-day window — won't re-send if already sent in last 6 days."""
    now = datetime.utcnow()
    since = now - timedelta(days=7)
    digest = _build_digest_data(since, now)

    members = User.query.filter_by(email_digest_opt_out=False).filter(
        (User.lifetime_access == True) | (User.subscription_status == "active")
    ).all()

    sent = 0
    skipped = 0
    for u in members:
        if u.last_digest_sent_at and (now - u.last_digest_sent_at) < timedelta(days=6):
            skipped += 1
            continue
        from flask import url_for
        try:
            unsub_url = url_for("toggle_digest", _external=True)
        except Exception:
            unsub_url = "#"
        send_weekly_digest(u, {**digest, "unsubscribe_url": unsub_url})
        u.last_digest_sent_at = now
        sent += 1
    db.session.commit()
    print(f"[DIGEST] sent={sent} skipped={skipped} total_members={len(members)}")
    return sent, skipped


@cron_cli.command("digest")
def cli_digest():
    """flask cron digest -- run the weekly digest."""
    run_weekly_digest()


@cron_cli.command("test-email")
def cli_test_email():
    """flask cron test-email -- send a test email to verify Resend wiring."""
    from email_send import send_email
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        click.echo("No admin user found - set ADMIN_EMAILS or create one.")
        return
    admin_email = admin.email
    send_email(to=admin_email, subject="Resend test", body_text="If you can read this, Resend is wired up correctly.", async_=False)
    click.echo(f"Sent to {admin_email}")
