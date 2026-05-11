"""Scheduled jobs and engagement email triggers.

Designed to be called from Railway Cron Jobs (or similar) via:
    flask digest         # weekly digest
    flask dm-notify <user_id> <sender_id>   # one-off DM email

Also exposes Python helpers used inline by route handlers
(e.g. notify_dm_throttled in features_routes.send_message).
"""
import os
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


# ===== Nightly reconciliation =====
#
# Belt-and-suspenders for the referral + billing pipeline. Catches state
# drift caused by missed Stripe webhooks, GHL writes that timed out, or
# guests who signed up before the Phase 1 attribution loop existed.
#
# Three independent jobs, each safe to run alone:
#   1. _reconcile_referrers    — patch User.referred_by from GHL contact
#   2. _reconcile_subscriptions — sync subscription_status from Stripe
#   3. _resync_ghl_active_members — re-push custom fields to GHL
#
# All three are idempotent; running twice in a row is a no-op the second
# pass (assuming nothing else changed).


def _reconcile_referrers(dry_run: bool = False) -> dict:
    """Find members with referred_by IS NULL and try to resolve them via GHL.

    Only touches users with a stripe_customer_id (i.e. real members, not
    pure prospects). Does NOT bump qualified_referrals_count retroactively
    — that would risk flipping referrers to lifetime based on payments
    that already happened, and Kashi explicitly didn't approve that.
    """
    # Lazy import — app imports cron at startup, so we can't top-level-import
    # app here without creating a circular dep.
    from app import _resolve_referrer_from_ghl

    candidates = (
        User.query
        .filter(User.referred_by.is_(None))
        .filter(User.stripe_customer_id.isnot(None))
        .all()
    )
    patched = 0
    skipped = 0
    for u in candidates:
        inviter_id = _resolve_referrer_from_ghl(u.email)
        if not inviter_id:
            skipped += 1
            continue
        if dry_run:
            click.echo(f"  [DRY] would patch {u.email}: referred_by = {inviter_id}")
            patched += 1
            continue
        u.referred_by = inviter_id
        patched += 1
    if not dry_run and patched:
        db.session.commit()
    return {"candidates": len(candidates), "patched": patched, "skipped": skipped}


def _reconcile_subscriptions(dry_run: bool = False) -> dict:
    """Pull live subscription status from Stripe for every member with a
    stripe_subscription_id, and update User.subscription_status if it drifted.

    Catches silent cancels (the customer canceled in the Stripe portal but
    our webhook never fired or never landed). Lifetime members are skipped
    — their sub was intentionally canceled at qualification, but they keep
    full access via lifetime_access=True; we never want to downgrade them.
    """
    import os
    import stripe as _stripe
    _stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not _stripe.api_key or "placeholder" in _stripe.api_key.lower():
        click.echo("  [skip] STRIPE_SECRET_KEY not configured.")
        return {"checked": 0, "drifted": 0, "errors": 0, "skipped_lifetime": 0}

    members = (
        User.query
        .filter(User.stripe_subscription_id.isnot(None))
        .all()
    )
    checked = 0
    drifted = 0
    errors = 0
    skipped_lifetime = 0
    for u in members:
        if u.lifetime_access:
            skipped_lifetime += 1
            continue
        try:
            sub = _stripe.Subscription.retrieve(u.stripe_subscription_id)
        except Exception as e:
            errors += 1
            click.echo(f"  [err] {u.email}: {e}")
            continue
        checked += 1
        new_status = sub.get("status") if isinstance(sub, dict) else getattr(sub, "status", None)
        if not new_status:
            continue
        if u.subscription_status != new_status:
            click.echo(f"  drift: {u.email} {u.subscription_status!r} -> {new_status!r}")
            drifted += 1
            if not dry_run:
                u.subscription_status = new_status
    if not dry_run and drifted:
        db.session.commit()
    return {
        "checked": checked, "drifted": drifted,
        "errors": errors, "skipped_lifetime": skipped_lifetime,
    }


def _resync_ghl_active_members(dry_run: bool = False) -> dict:
    """Re-push custom_fields_from_user to GHL for every active member so
    payments_made_count / qualified_referrals_count / lifetime_access never
    drift from the SQL truth. Each upsert is fire-and-forget (daemon thread)
    inside lib/ghl, so this is rate-friendly even on large rosters.
    """
    from lib import ghl as _ghl

    actives = (
        User.query
        .filter((User.lifetime_access == True) | (User.subscription_status == "active"))
        .all()
    )
    pushed = 0
    for u in actives:
        if dry_run:
            pushed += 1
            continue
        stage = "lifetime-qualified" if u.lifetime_access else "active-member"
        try:
            _ghl.upsert_contact(
                email=u.email,
                name=u.name or "",
                stage_tag=stage,
                custom_fields=_ghl.custom_fields_from_user(u),
            )
            pushed += 1
        except Exception as e:
            click.echo(f"  [err] ghl resync {u.email}: {e}")
    return {"actives": len(actives), "pushed": pushed}


def run_nightly_reconcile(dry_run: bool = False) -> dict:
    """Orchestrator — runs all three reconciliation jobs and returns combined stats."""
    click.echo(f"[RECONCILE] dry_run={dry_run}")
    click.echo("  referrer reconciliation...")
    ref_stats = _reconcile_referrers(dry_run=dry_run)
    click.echo(f"  -> {ref_stats}")
    click.echo("  subscription reconciliation...")
    sub_stats = _reconcile_subscriptions(dry_run=dry_run)
    click.echo(f"  -> {sub_stats}")
    click.echo("  ghl resync...")
    ghl_stats = _resync_ghl_active_members(dry_run=dry_run)
    click.echo(f"  -> {ghl_stats}")
    return {"referrer": ref_stats, "subscription": sub_stats, "ghl": ghl_stats}


@cron_cli.command("reconcile")
@click.option("--dry-run", is_flag=True, help="Print intended changes without writing.")
def cli_reconcile(dry_run):
    """flask cron reconcile [--dry-run] -- nightly reconciliation sweep.

    Patches missing referred_by from GHL, syncs subscription_status from
    Stripe, and re-pushes custom fields to GHL contact records. Idempotent.
    """
    run_nightly_reconcile(dry_run=dry_run)


# ===== Team auto-post queue (Phase 14) =====
#
# The Sovereign Society Team user (prod id=11, email team@sovereignsociety.rich)
# publishes one queued post to each Space at an every-other-day cadence
# (TEAM_POST_CADENCE_DAYS env var, default 2). Cron runs daily; the
# per-Space cadence check prevents double-firing.
#
# - Strict FIFO by (queue_position ASC, created_at ASC).
# - One post per Space per cron run, at most.
# - Reads "last team post" from the `post` table (not the queue) — so the
#   123 backdated Phase 12 posts naturally respect cadence too.
# - Does NOT fire notifications, GHL pushes, or engagement tagging.
# - Does NOT delete published queue rows; transitions pending → published
#   with `published_post_id` + `published_at` set for audit.

@cron_cli.command("team-post-publish")
def cli_team_post_publish():
    """Publish next-in-queue Team posts for each Space whose cadence is up.

    Cadence: TEAM_POST_CADENCE_DAYS env var (default 2). A Space gets a new
    post only if its most recent Team post is older than that.
    """
    from models import Space, Post, TeamPostQueue

    team = User.query.filter_by(email="team@sovereignsociety.rich").first()
    if not team:
        click.echo("[TEAM-POST] Team user (team@sovereignsociety.rich) not found. Aborting.")
        return

    cadence = int(os.environ.get("TEAM_POST_CADENCE_DAYS", "2"))
    cadence_delta = timedelta(days=cadence)
    now = datetime.utcnow()
    threshold = now - cadence_delta

    published = 0
    skipped_too_recent = 0
    skipped_empty_queue = 0

    for space in Space.query.order_by(Space.id).all():
        last = (
            Post.query
            .filter_by(user_id=team.id, space_id=space.id)
            .order_by(Post.created_at.desc())
            .first()
        )
        if last and last.created_at and last.created_at > threshold:
            skipped_too_recent += 1
            continue

        next_q = (
            TeamPostQueue.query
            .filter_by(space_id=space.id, status="pending")
            .order_by(TeamPostQueue.queue_position.asc(), TeamPostQueue.created_at.asc())
            .first()
        )
        if not next_q:
            skipped_empty_queue += 1
            continue

        p = Post(
            user_id=team.id,
            space_id=space.id,
            content=next_q.content,
            created_at=now,
            updated_at=now,
        )
        db.session.add(p)
        db.session.flush()  # populate p.id before linking
        next_q.status = "published"
        next_q.published_post_id = p.id
        next_q.published_at = now
        published += 1
        preview = next_q.content[:70].replace("\n", " ")
        click.echo(f"[TEAM-POST] published in {space.name!r}: {preview!r}")

    db.session.commit()
    click.echo(
        f"[TEAM-POST] cadence={cadence}d  published={published}  "
        f"skipped_recent={skipped_too_recent}  skipped_empty={skipped_empty_queue}"
    )
