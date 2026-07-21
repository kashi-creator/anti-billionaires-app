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


# ===== Paid-but-no-account reminders =====
#
# Stripe Checkout creates a Customer + Subscription BEFORE the app account
# exists — the User row (with password) is only created when the buyer
# completes the /subscription/success form. A buyer who closes the tab right
# after paying ends up with a live Stripe subscription and NO login.
#
# This job finds those people and emails them a link back to finish signup.
#   - Only subs in a paid-ish state (trialing/active/past_due/unpaid).
#   - Skip subs younger than MIN_AGE_HOURS (give them time to finish on their
#     own) or older than MAX_AGE_DAYS (stale — stop chasing).
#   - Dedup via Stripe customer metadata (signup_reminder_count /
#     signup_reminder_last_at): at most MAX reminders, spaced >= SPACING_HOURS.
# Idempotent and safe to run daily.

SIGNUP_REMINDER_MIN_AGE_HOURS = 2
SIGNUP_REMINDER_MAX_AGE_DAYS = 14
SIGNUP_REMINDER_MAX = 3
SIGNUP_REMINDER_SPACING_HOURS = 48
_SIGNUP_LIVE_STATUSES = {"trialing", "active", "past_due", "unpaid"}


def _remind_paid_no_account(dry_run: bool = False) -> dict:
    """Email Stripe subscribers who never created an app account."""
    import stripe as _stripe
    from flask import url_for
    from email_send import send_complete_signup_reminder

    _stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not _stripe.api_key or "placeholder" in _stripe.api_key.lower():
        click.echo("  [skip] STRIPE_SECRET_KEY not configured.")
        return {"checked": 0, "candidates": 0, "reminded": 0, "skipped": 0}

    now = datetime.utcnow()
    min_age = timedelta(hours=SIGNUP_REMINDER_MIN_AGE_HOURS)
    max_age = timedelta(days=SIGNUP_REMINDER_MAX_AGE_DAYS)
    spacing = timedelta(hours=SIGNUP_REMINDER_SPACING_HOURS)

    checked = candidates = reminded = skipped = 0
    subs = _stripe.Subscription.list(status="all", limit=100, expand=["data.customer"])
    for sub in subs.auto_paging_iter():
        checked += 1
        if sub.get("status") not in _SIGNUP_LIVE_STATUSES:
            continue
        cust = sub.get("customer")
        if not isinstance(cust, dict) or cust.get("deleted"):
            continue
        email = (cust.get("email") or (cust.get("metadata") or {}).get("signup_email") or "").strip().lower()
        if not email:
            continue
        # Has an app account already? Then nothing to do.
        if User.query.filter_by(email=email).first():
            continue
        # Age window.
        age = now - datetime.utcfromtimestamp(sub.get("created", 0))
        if age < min_age or age > max_age:
            skipped += 1
            continue
        # Reminder throttle (stored on the Stripe customer).
        meta = cust.get("metadata") or {}
        count = int(meta.get("signup_reminder_count") or 0)
        if count >= SIGNUP_REMINDER_MAX:
            skipped += 1
            continue
        last_raw = meta.get("signup_reminder_last_at")
        if last_raw:
            try:
                if now - datetime.fromisoformat(last_raw) < spacing:
                    skipped += 1
                    continue
            except (ValueError, TypeError):
                pass
        # Build the finish-signup link from their most recent checkout session.
        sess_id = None
        try:
            sessions = _stripe.checkout.Session.list(customer=cust["id"], limit=1)
            if sessions.data:
                sess_id = sessions.data[0].id
        except Exception as e:
            click.echo(f"  [warn] no checkout session for {email}: {e}")
        if not sess_id:
            skipped += 1
            continue
        complete_url = url_for("subscription_success", session_id=sess_id, _external=True)
        name = cust.get("name") or email.split("@")[0]
        candidates += 1
        if dry_run:
            click.echo(f"  [DRY] would remind {email} (age {age.days}d, sent {count} so far) -> {complete_url}")
            reminded += 1
            continue
        if send_complete_signup_reminder(email, name, complete_url, async_=False):
            reminded += 1
            try:
                _stripe.Customer.modify(cust["id"], metadata={
                    "signup_reminder_count": str(count + 1),
                    "signup_reminder_last_at": now.isoformat(),
                })
            except Exception as e:
                click.echo(f"  [warn] reminder metadata update failed for {email}: {e}")
        else:
            click.echo(f"  [err] reminder email failed for {email}")
    return {"checked": checked, "candidates": candidates, "reminded": reminded, "skipped": skipped}


def run_nightly_reconcile(dry_run: bool = False) -> dict:
    """Orchestrator — runs all reconciliation jobs and returns combined stats."""
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
    click.echo("  paid-but-no-account reminders...")
    rem_stats = _remind_paid_no_account(dry_run=dry_run)
    click.echo(f"  -> {rem_stats}")
    return {"referrer": ref_stats, "subscription": sub_stats, "ghl": ghl_stats, "signup_reminders": rem_stats}


@cron_cli.command("reconcile")
@click.option("--dry-run", is_flag=True, help="Print intended changes without writing.")
def cli_reconcile(dry_run):
    """flask cron reconcile [--dry-run] -- nightly reconciliation sweep.

    Patches missing referred_by from GHL, syncs subscription_status from
    Stripe, re-pushes custom fields to GHL, and reminds paid-but-no-account
    buyers to finish signup. Idempotent.
    """
    run_nightly_reconcile(dry_run=dry_run)


@cron_cli.command("signup-reminders")
@click.option("--dry-run", is_flag=True, help="List who would be reminded without sending.")
def cli_signup_reminders(dry_run):
    """flask cron signup-reminders [--dry-run] -- email buyers who paid via
    Stripe but never finished creating their app account.

    Runs automatically as part of `flask cron reconcile`; this standalone
    command is for manual runs and dry-run testing.
    """
    stats = _remind_paid_no_account(dry_run=dry_run)
    click.echo(f"[SIGNUP-REMINDERS] {stats}")


# ===== Meeting invite + day-of reminder =====
# Flask-owned event driver (the GHL CLI can't do calendar-aware sends). Reads
# the next upcoming St. Pete chapter event from the DB and sends SMS via GHL
# Conversations:
#   - T-2 days: invite the sms-opted-in prospects to the next Thursday.
#   - day-of:   remind the meeting-rsvp guests it's tonight.
# Idempotent via per-event GHL marker tags (invited-<date> / reminded-<date>),
# so re-running never double-sends. SMS only to contacts that have a phone.
# Schedule: run daily ~9am ET (13:00 UTC).

def run_meeting_reminders(dry_run: bool = False) -> dict:
    from lib import ghl
    from models import Event
    today = datetime.utcnow().date()
    ev = (
        Event.query
        .filter(Event.event_type == "chapter_recurring",
                Event.is_recurrence_template == False,
                Event.date >= today)
        .order_by(Event.date.asc())
        .first()
    )
    if not ev:
        click.echo("[MEETING] no upcoming chapter event; nothing to do.")
        return {"event": None, "invited": 0, "reminded": 0}

    days_out = (ev.date - today).days
    ds = ev.date.isoformat()
    when_day = ev.date.strftime("%A")
    when_time = ev.time or "6:30 PM"
    where = ev.location or "The Temple, 155 8th St N, St. Pete"

    if days_out not in (0, 2):
        click.echo(f"[MEETING] next event {ds} is {days_out}d out (not 0 or 2); nothing to send.")
        return {"event": ds, "days_out": days_out, "invited": 0, "reminded": 0}

    # Quiet-hours guard: never send outside ~8am-8pm ET even if the cron fires
    # at an odd hour. Fail-safe — skips the day rather than texting at 5am.
    if not dry_run:
        try:
            from zoneinfo import ZoneInfo
            et_hour = datetime.now(ZoneInfo("America/New_York")).hour
        except Exception:
            et_hour = (datetime.utcnow().hour - 4) % 24
        if not (8 <= et_hour <= 20):
            click.echo(f"[MEETING] {et_hour:02d}:00 ET is outside the 8-20 send window; skipping.")
            return {"event": ds, "days_out": days_out, "invited": 0, "reminded": 0, "skipped_quiet_hours": True}

    contacts = ghl.list_contacts()
    invited = reminded = 0

    if days_out == 2:
        marker = f"invited-{ds}"
        msg = (f"{when_day}. {when_time}. {where}. The table fills with men who "
               f"refuse to be average. First two are on us. You in?")
        for c in contacts:
            tags = {(t or '').lower() for t in (c.get('tags') or [])}
            if {'sms-opted-in', 'prospect'} <= tags and marker not in tags and c.get('phone'):
                if dry_run:
                    invited += 1
                    continue
                if ghl.send_sms_to_contact(contact_id=c['id'], message=msg):
                    ghl._add_tags(c['id'], [marker])
                    invited += 1
    elif days_out == 0:
        marker = f"reminded-{ds}"
        msg = f"Tonight. {when_time}. {where}. The table's set. Bring nothing but your presence."
        for c in contacts:
            tags = {(t or '').lower() for t in (c.get('tags') or [])}
            if 'meeting-rsvp' in tags and marker not in tags and c.get('phone'):
                if dry_run:
                    reminded += 1
                    continue
                if ghl.send_sms_to_contact(contact_id=c['id'], message=msg):
                    ghl._add_tags(c['id'], [marker])
                    reminded += 1

    click.echo(f"[MEETING] event={ds} days_out={days_out} invited={invited} reminded={reminded} dry_run={dry_run}")
    return {"event": ds, "days_out": days_out, "invited": invited, "reminded": reminded}


@cron_cli.command("meeting-reminders")
@click.option("--dry-run", is_flag=True, help="Count who would be messaged without sending.")
def cli_meeting_reminders(dry_run):
    """flask cron meeting-reminders [--dry-run] -- invite (T-2) + day-of reminder
    for the next St. Pete chapter meeting. Idempotent via GHL marker tags. Run
    daily ~9am ET (13:00 UTC)."""
    run_meeting_reminders(dry_run=dry_run)


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
