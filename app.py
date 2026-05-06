import os
import uuid
import json
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
import bcrypt
import secrets
import stripe
from datetime import timedelta
from email_send import (
    send_email, send_welcome_verify, send_password_reset,
    send_payment_succeeded, send_payment_failed, send_lifetime_unlocked,
)
from models import (
    db, User, Post, Comment, Like, Follow, Space, SpaceMembership,
    Notification, Poll, PollOption, PollVote,
    Event, EventRSVP, Course, Lesson, LessonProgress,
    ChecklistItem, UserChecklist,
    Conversation, Message, Story, StoryView,
    Win, WinReaction, Deal, DealInterest,
    WeeklyChallenge, ChallengeSubmission, ChallengeVote,
    Resource, ResourceUpvote, MemberGoal, AccountabilityPair, GoalCheckIn,
    Bookmark, Badge, UserBadge, Reel, SpaceChat, AIChat,
    Availability, CallBooking, Activity, StripeEvent, DeviceToken,
    AssessmentResponse,
    Project,
)
from phase3_routes import phase3, seed_checklist
from features_routes import features, seed_badges, check_and_award_badges
from lib import ghl
from lib import assessment as assessment_lib
from lib import push as push_lib

app = Flask(__name__)

ENV = os.environ.get("FLASK_ENV", "development")
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if ENV == "production":
        raise RuntimeError("SECRET_KEY must be set in production")
    SECRET_KEY = "dev-only-not-for-prod-change-me"
    print("[WARN] Using insecure dev SECRET_KEY. Set SECRET_KEY env var for production.")
app.config["SECRET_KEY"] = SECRET_KEY

_db_url = os.environ.get("DATABASE_URL", "sqlite:///abmc.db")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

if _db_url.startswith("postgresql://"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 1800,
    }

app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")

# SERVER_NAME enables `url_for(..., _external=True)` to resolve outside a
# request context (e.g. inside email-rendering daemon threads, CLI commands
# like `flask cron digest`). Without it, those code paths throw RuntimeError
# and the HTML email body silently fails to render. Set the env var in
# Railway to the canonical host; locally we leave it None so dev binding
# to 127.0.0.1:5000 keeps working.
app.config["SERVER_NAME"] = os.environ.get("SERVER_NAME") or (
    "anti-billionaires-app-production.up.railway.app" if ENV == "production" else None
)
app.config["PREFERRED_URL_SCHEME"] = "https"

# Session cookie hardening
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = ENV == "production"
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30  # 30 days
app.config["REMEMBER_COOKIE_HTTPONLY"] = True
app.config["REMEMBER_COOKIE_SECURE"] = ENV == "production"
app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"

# CSRF: disabled by default for legacy compat; auth-critical routes opt in
# manually via validate_csrf(). Forms can still call {{ csrf_token() }} since
# CSRFProtect is initialized below — making templates ready for full rollout.
app.config["WTF_CSRF_CHECK_DEFAULT"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None  # session-bound

# Stripe config
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_placeholder")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "price_placeholder")
stripe.api_key = STRIPE_SECRET_KEY

# GHL config — env vars are read inside lib/ghl.py at call time.
# `GHL_API_KEY` and `GHL_LOCATION_ID` are required for live writes; if either
# is unset the client no-ops. Pipeline / stage IDs are optional (Phase 2 scope).

db.init_app(app)
migrate = Migrate(app, db)

csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],  # opt-in per route via @limiter.limit
    storage_uri="memory://",
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "pricing"


@app.context_processor
def _inject_csrf_token():
    return {"csrf_token": generate_csrf}


def _is_native_app_request():
    """True when the request is coming from the Capacitor native shell.
    Used to hide signup/checkout CTAs in the iOS app (Apple 'reader' rule).
    Capacitor sets a custom UA prefix; we also accept an explicit X-Native header."""
    ua = (request.user_agent.string or "").lower()
    if request.headers.get("X-Native-App") == "1":
        return True
    return "capacitor" in ua or "1%mc-native" in ua or "sovereign-native" in ua


@app.context_processor
def _inject_native_flag():
    try:
        return {"is_native_app": _is_native_app_request()}
    except RuntimeError:
        return {"is_native_app": False}


def require_csrf(f):
    """Enforce CSRF on a route. Used while WTF_CSRF_CHECK_DEFAULT is False.

    Accepts the token via either the form field ``csrf_token`` or the
    ``X-CSRFToken`` header (Flask-WTF's canonical header) so JSON fetch
    callers can pass the token without form-encoding their body.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == "POST" and app.config.get("WTF_CSRF_ENABLED", True):
            token = (
                request.form.get("csrf_token")
                or request.headers.get("X-CSRFToken")
                or request.headers.get("X-CSRF-Token")
                or ""
            )
            try:
                validate_csrf(token)
            except Exception:
                abort(400, description="Invalid or missing CSRF token")
        return f(*args, **kwargs)
    return wrapper


app.register_blueprint(phase3)
app.register_blueprint(features)

from cron import cron_cli
app.cli.add_command(cron_cli)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


# ===== HELPERS =====

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        return f"uploads/{filename}"
    return None


def create_notification(user_id, type, message, link=None):
    """Helper to create a notification for a user."""
    if user_id == current_user.id:
        return  # Don't notify yourself
    notif = Notification(user_id=user_id, type=type, message=message, link=link)
    db.session.add(notif)
    push_lib.send_push_to_user(user_id, "Sovereign", message, link or "/notifications")


def _admin_email_allowlist():
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        # Defense in depth: if ADMIN_EMAILS env is set, require membership.
        allowlist = _admin_email_allowlist()
        if allowlist and current_user.email.lower() not in allowlist:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def paywall_required(f):
    """Block route until user has active subscription or lifetime access.
    Stacks on @login_required; if missing access, redirect to /pricing."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        if not current_user.has_active_subscription:
            flash("Membership required to access this area.", "warning")
            return redirect(url_for("pricing"))
        if not current_user.onboarding_complete:
            return redirect(url_for("onboarding"))
        return f(*args, **kwargs)
    return wrapper


def subscription_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.has_active_subscription:
            flash("This feature requires an active membership.", "error")
            return redirect(url_for("pricing"))
        return f(*args, **kwargs)
    return decorated


# ===== GHL INTEGRATION =====
# All GHL writes go through `lib/ghl.py` (Phase 1). Stage tags only — see
# INTEGRATION-SOURCE-OF-TRUTH.md §6 for the canonical taxonomy.


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Schema is now managed by Flask-Migrate (alembic).
# In dev: db.create_all() bootstraps a fresh sqlite DB.
# In prod: `flask db upgrade` runs at container start before gunicorn (railway.json startCommand).
# Seed calls are wrapped so module import doesn't fail if the DB isn't reachable yet
# (e.g. during build, or while migrations are still running).
with app.app_context():
    try:
        if _db_url.startswith("sqlite:"):
            db.create_all()
        seed_checklist()
        seed_badges()
    except Exception as _seed_err:
        print(f"[STARTUP] Seed deferred: {_seed_err}", flush=True)


def _next_weekday(anchor, weekday):
    """Return the first date >= anchor whose weekday() matches `weekday` (0=Mon..6=Sun)."""
    delta = (weekday - anchor.weekday()) % 7
    return anchor + timedelta(days=delta)


def _first_thursday_of(year, month):
    """Date of the 1st Thursday in (year, month)."""
    return _next_weekday(date(year, month, 1), 3)


def _last_thursday_of(year, month):
    """Date of the last Thursday in (year, month)."""
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    last_day = next_month_first - timedelta(days=1)
    delta = (last_day.weekday() - 3) % 7
    return last_day - timedelta(days=delta)


def _generate_upcoming_occurrences(template, weeks_ahead=8):
    """Idempotently materialize the next `weeks_ahead` weeks of occurrences for a recurring template Event.

    For each calendar date implied by the template's recurrence_rule that falls in
    [today, today + weeks_ahead*7], create a child Event row pointing back at the template
    (recurrence_parent_id=template.id, recurrence_rule="none", is_recurrence_template=False).
    Existing child rows for the same date are skipped — safe to call repeatedly.

    Per-occurrence rows preserve EventRSVP joins by event_id so members RSVP to a specific date.
    Time/location are inherited from the template; admins can edit per-occurrence to vary
    (e.g. the Thursday lunch alternates location each week).
    """
    if not template.is_recurrence_template:
        return 0
    rule = template.recurrence_rule
    if rule == "none":
        return 0

    today = date.today()
    horizon = today + timedelta(weeks=weeks_ahead)

    target_dates = []
    if rule == "every_thursday":
        d = _next_weekday(today, 3)
        while d <= horizon:
            target_dates.append(d)
            d += timedelta(days=7)
    elif rule == "first_and_last_thursday_monthly":
        # Walk months forward until past the horizon
        y, m = today.year, today.month
        while True:
            for d in (_first_thursday_of(y, m), _last_thursday_of(y, m)):
                if today <= d <= horizon and d not in target_dates:
                    target_dates.append(d)
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
            if date(y, m, 1) > horizon:
                break
    else:
        return 0

    existing_dates = {
        d for (d,) in db.session.query(Event.date).filter(
            Event.recurrence_parent_id == template.id
        ).all()
    }

    created = 0
    for d in sorted(target_dates):
        if d in existing_dates:
            continue
        child = Event(
            title=template.title,
            description=template.description,
            date=d,
            time=template.time or "",
            location=template.location or "",
            host_id=template.host_id,
            cover_image=template.cover_image,
            event_type=template.event_type,
            chapter=template.chapter,
            recurrence_rule="none",
            recurrence_parent_id=template.id,
            is_recurrence_template=False,
        )
        db.session.add(child)
        created += 1
    return created


def _seed_content():
    """Populate spaces, events, and posts. Idempotent - checks before inserting."""
    # --- Ensure a system/admin user exists for authored content ---
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        admin = User.query.first()
    if not admin:
        # No users at all yet - skip seeding authored content
        return
    admin_id = admin.id

    # --- One-time space renames (legacy titles → current titles) ---
    # Why: titles updated post-launch; existing rows must be renamed in place
    #      so member activity (posts, joins) carries over.
    _space_rename_map = {
        "Brotherhood Ops": "Business Directory",
        "Red Pill Intel": "The Hidden Truth",
    }
    for _old, _new in _space_rename_map.items():
        legacy = Space.query.filter_by(name=_old).first()
        if not legacy:
            continue
        if Space.query.filter_by(name=_new).first():
            db.session.delete(legacy)
        else:
            legacy.name = _new
    db.session.commit()

    # --- SPACES ---
    spaces_data = [
        ("Sovereign Wealth", "Building outside the rigged casino. Business, crypto, real assets, off-grid income streams. We build wealth they can't print away.", "img/seed/space-sovereign-wealth.png"),
        ("Body & Iron", "Fitness, nutrition, cutting the poison. Real food, real training, real results. Your body is your first empire.", "img/seed/space-body-iron.png"),
        ("Awake Minds", "Suppressed knowledge, psychedelics, consciousness, and our place in the cosmos. Question everything. Accept nothing at face value.", "img/seed/space-awake-minds.png"),
        ("Business Directory", "Supporting each other's businesses, referrals, accountability. We rise together or not at all.", "img/seed/space-brotherhood-ops.png"),
        ("The Arsenal", "2A discussion, preparedness, self-defense, personal sovereignty. The ultimate safeguard of a free people.", "img/seed/space-arsenal.png"),
        ("The Hidden Truth", "Elite corruption, trafficking, media lies, what they don't want you to see. Drag the truth into the light.", "img/seed/space-red-pill-intel.png"),
        ("Family & Legacy", "Raising strong children, protecting your bloodline, building generational wealth. What you build must outlast you.", "img/seed/space-family-legacy.png"),
        ("Off Grid", "Growing real food, land ownership, self-sufficiency, decentralization. Break the dependency chain.", "img/seed/space-off-grid.png"),
    ]
    for name, desc, cover_image in spaces_data:
        existing = Space.query.filter_by(name=name).first()
        if existing:
            if not existing.cover_image:
                existing.cover_image = cover_image
        else:
            space = Space(name=name, description=desc, cover_image=cover_image, created_by=admin_id)
            db.session.add(space)
    db.session.commit()

    # --- EVENTS (Phase 3 rework) ---
    # Wipe stale Phase 0B events. Pre-real-traffic; no real RSVPs to lose.
    # The cascade on Event.rsvps drops any seed RSVPs along with each row.
    stale_titles = ["Fire to Fire - St. Pete", "Sovereign Wealth Workshop", "Brotherhood Summit"]
    stale = Event.query.filter(
        Event.title.in_(stale_titles), Event.recurrence_parent_id.is_(None)
    ).all()
    for ev in stale:
        db.session.delete(ev)
    if stale:
        db.session.flush()

    today = date.today()
    st_pete_anchor = _first_thursday_of(today.year, today.month)
    if st_pete_anchor < today:
        ny, nm = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        st_pete_anchor = _first_thursday_of(ny, nm)
    next_thursday = _next_weekday(today, 3)
    if next_thursday == today:
        next_thursday = today + timedelta(days=7)

    def _seed_recurring_template(*, title, description, anchor_date, time, location,
                                 event_type, chapter, recurrence_rule):
        existing = Event.query.filter_by(title=title, is_recurrence_template=True).first()
        if existing:
            return existing
        template = Event(
            title=title,
            description=description,
            date=anchor_date,
            time=time,
            location=location,
            host_id=admin_id,
            event_type=event_type,
            chapter=chapter,
            recurrence_rule=recurrence_rule,
            is_recurrence_template=True,
        )
        db.session.add(template)
        db.session.flush()
        return template

    st_pete_template = _seed_recurring_template(
        title="St. Petersburg Chapter Biweekly",
        description=(
            "Sovereign Society's St. Petersburg chapter biweekly meetup. The 1st and last Thursday of every month. "
            "Brotherhood, accountability, and discussion. Open to all members."
        ),
        anchor_date=st_pete_anchor,
        time="6:30 PM EST",
        location="The Temple, 155 8th Street North, Saint Petersburg, FL 33701",
        event_type="chapter_recurring",
        chapter="St. Petersburg, FL",
        recurrence_rule="first_and_last_thursday_monthly",
    )
    lunch_template = _seed_recurring_template(
        title="Thursday Group Lunch",
        description=(
            "Weekly Thursday group lunch. Time and location alternate each week — confirm via the specific "
            "Thursday's event card before showing up."
        ),
        anchor_date=next_thursday,
        time="",
        location="",
        event_type="weekly_recurring",
        chapter="Global",
        recurrence_rule="every_thursday",
    )
    db.session.commit()

    # Materialize the next 8 weeks of occurrences for both templates.
    _generate_upcoming_occurrences(st_pete_template, weeks_ahead=8)
    _generate_upcoming_occurrences(lunch_template, weeks_ahead=8)
    db.session.commit()

    # --- POSTS ---
    manifesto_content = (
        "We are living in an engineered reality. The food is poisoned, the money is fake and not worth "
        "the paper it's printed on, history is sanitized, and our men are weak. The architects of this "
        "system do not want you strong, sovereign, or awake. They want you medicated, dependent, and "
        "distracted. We refuse the terms of this surrender.\n\n"
        "This is not a political movement; it is a reclamation of masculine power. We are a brotherhood "
        "of builders, thinkers, and protectors who have chosen to step out of the chaos and into purpose. "
        "But we do not just complain about the dark; we build the fire.\n\n"
        "We are here to build sovereign wealth outside their rigged casinos. We are here to empower the "
        "men who grow real food in real soil. We are here to support each other's businesses, passions, "
        "fitness, consciousness, and families. We are here to forge unbreakable bonds of brotherhood in "
        "an age of profound isolation.\n\n"
        "If you are comfortable with your life inside the matrix, stay where you are. If you are ready "
        "to do the real work then strap in."
    )

    welcome_content = (
        "Welcome to Sovereign Society. If you are here, you chose to wake up. "
        "Introduce yourself - who are you, what are you building, and what are you done tolerating? "
        "This is your brotherhood. Show up. Speak truth. Build fire."
    )

    challenge_content = (
        "WEEKLY CHALLENGE: This week - cut one processed food from your diet entirely. Replace it "
        "with something you grew or sourced locally. Report back Sunday with what you chose and how "
        "it felt. The body is the first empire we reclaim."
    )

    posts_data = [
        ("THE MANIFESTO", manifesto_content),
        ("WELCOME", welcome_content),
        ("WEEKLY CHALLENGE", challenge_content),
    ]
    for tag, content in posts_data:
        # Use a prefix marker in content to identify seeded posts
        marker = f"[SEED:{tag}]"
        if not Post.query.filter(Post.content.contains(content[:80])).first():
            post = Post(user_id=admin_id, content=content)
            db.session.add(post)
    db.session.commit()

    print("[SEED] Content seeding complete.")


with app.app_context():
    try:
        _seed_content()
    except Exception as e:
        # Don't block app startup if seeding fails (e.g., during migrations
        # when schema is mid-upgrade or fresh DB without users yet).
        print(f"[SEED] Skipped: {e}")


# --- Routes ---

@app.route("/")
def index():
    if current_user.is_authenticated and current_user.has_active_subscription:
        if not current_user.onboarding_complete:
            return redirect(url_for("onboarding"))
        return redirect(url_for("feed"))
    if current_user.is_authenticated:
        # Authenticated but no membership: send to pricing.
        return redirect(url_for("pricing"))
    return render_template("landing.html")


@app.route("/service-worker.js")
def service_worker():
    """Serve service-worker.js from root so its scope covers the entire app
    (a SW served from /static can only control /static)."""
    from flask import send_from_directory, make_response
    resp = make_response(send_from_directory(
        os.path.join(app.root_path, "static", "js"),
        "service-worker.js",
        mimetype="application/javascript",
    ))
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/offline")
def offline_page():
    """Lightweight fallback rendered by the SW when navigation fails."""
    return render_template("errors/offline.html"), 200


@app.context_processor
def _inject_vapid_public_key():
    return {"vapid_public_key": push_lib.vapid_public_key()}


@app.route("/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    """Browser PushManager subscription is POSTed here as JSON:
    {endpoint, keys: {p256dh, auth}}. We upsert by endpoint so re-subscribes
    don't create duplicates."""
    payload = request.get_json(silent=True) or {}
    endpoint = (payload.get("endpoint") or "").strip()
    keys = payload.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()

    if not endpoint or not p256dh or not auth:
        return jsonify({"success": False, "error": "Missing subscription fields"}), 400

    from models import PushSubscription
    now = datetime.utcnow()
    ua = request.headers.get("User-Agent", "")[:300]

    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.user_id = current_user.id
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = ua
        existing.last_seen_at = now
    else:
        db.session.add(PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=ua,
            created_at=now,
            last_seen_at=now,
        ))
    db.session.commit()
    return jsonify({"success": True})


@app.route("/push/unsubscribe", methods=["POST"])
@login_required
def push_unsubscribe():
    payload = request.get_json(silent=True) or {}
    endpoint = (payload.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"success": False}), 400
    from models import PushSubscription
    PushSubscription.query.filter_by(user_id=current_user.id, endpoint=endpoint).delete()
    db.session.commit()
    return jsonify({"success": True})


@app.route("/push/debug")
@login_required
def push_debug():
    """Quick diagnostic — surfaces server-side push state for the current user
    so we don't have to guess what's broken from the frontend."""
    from models import PushSubscription
    pk = push_lib.vapid_public_key()
    subs = PushSubscription.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "push_configured": push_lib.push_configured(),
        "vapid_public_key_present": bool(pk),
        "vapid_public_key_first16": pk[:16] if pk else None,
        "vapid_claim_email_set": bool(os.environ.get("VAPID_CLAIM_EMAIL")),
        "subscriptions_for_this_user": len(subs),
        "subscription_endpoints_first40": [s.endpoint[:40] + "..." for s in subs],
        "user_agent": request.headers.get("User-Agent", "")[:200],
        "is_https": request.is_secure,
    })


@app.route("/push/test", methods=["POST"])
@login_required
def push_test():
    """Self-send a push to verify end-to-end delivery. No-ops cleanly when
    push isn't configured so the user sees a clear error instead of silence."""
    if not push_lib.push_configured():
        return jsonify({"success": False, "error": "Push not configured on the server."}), 400
    from models import PushSubscription
    if not PushSubscription.query.filter_by(user_id=current_user.id).count():
        return jsonify({"success": False, "error": "No push subscription on file. Tap Enable first."}), 400
    push_lib.send_push_to_user(
        current_user.id,
        "Sovereign",
        "Push notifications are working. You're set.",
        "/notifications",
    )
    return jsonify({"success": True})


@app.route("/api/devices/register", methods=["POST"])
@login_required
def register_device():
    """Native apps POST {token, platform} after Capacitor push registration."""
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or "").strip()
    platform = (payload.get("platform") or "").strip().lower()
    if not token or platform not in ("ios", "android"):
        return jsonify({"success": False, "error": "Invalid token/platform"}), 400

    existing = DeviceToken.query.filter_by(token=token).first()
    now = datetime.utcnow()
    if existing:
        existing.user_id = current_user.id
        existing.platform = platform
        existing.last_seen_at = now
    else:
        db.session.add(DeviceToken(
            user_id=current_user.id, token=token, platform=platform,
            created_at=now, last_seen_at=now,
        ))
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/devices/unregister", methods=["POST"])
@login_required
def unregister_device():
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or "").strip()
    if not token:
        return jsonify({"success": False}), 400
    DeviceToken.query.filter_by(user_id=current_user.id, token=token).delete()
    db.session.commit()
    return jsonify({"success": True})


@app.route("/preferences/digest", methods=["GET", "POST"])
@login_required
@require_csrf
def toggle_digest():
    if request.method == "POST":
        current_user.email_digest_opt_out = not current_user.email_digest_opt_out
        db.session.commit()
        flash("Email preferences updated.", "success")
        return redirect(request.referrer or url_for("feed"))
    # GET: one-click unsubscribe link from emails toggles off and confirms
    current_user.email_digest_opt_out = True
    db.session.commit()
    return render_template("digest_unsubscribed.html")


@app.route("/terms")
def terms():
    return render_template("legal.html", title="Terms of Service", body_template="legal_terms")


@app.route("/privacy")
def privacy():
    return render_template("legal.html", title="Privacy Policy", body_template="legal_privacy")


@app.route("/manifesto")
@login_required
@paywall_required
def manifesto():
    from phase3_routes import _check_item_by_slug
    _check_item_by_slug(current_user.id, "read-manifesto")
    return render_template("manifesto.html")


# ===== Phase 5 — Self-Assessment =====
# Runs BEFORE the 5-step onboarding for new signups. Re-takeable from /assessment.
# NOTE: cannot use @paywall_required here — that decorator forces a redirect to
# /onboarding when onboarding is incomplete, which would loop assessment users
# straight past the assessment. Instead we mirror /onboarding's pattern:
# @login_required + manual has_active_subscription check.


def _post_signup_redirect(user):
    """Where to send a freshly-signed-up user.

    Flow: assessment (40q) → onboarding (5 steps) → feed.
    Returns a Flask redirect Response.
    """
    if not getattr(user, "assessment_complete", False):
        return redirect(url_for("assessment"))
    if not getattr(user, "onboarding_complete", False):
        return redirect(url_for("onboarding"))
    return redirect(url_for("feed"))


def _post_signup_redirect_url(user):
    """URL-string variant for JSON callers (e.g. /signup-with-code)."""
    if not getattr(user, "assessment_complete", False):
        return url_for("assessment")
    if not getattr(user, "onboarding_complete", False):
        return url_for("onboarding")
    return url_for("feed")


@app.route("/assessment", methods=["GET"])
@login_required
def assessment():
    if not current_user.has_active_subscription:
        return redirect(url_for("pricing"))
    return render_template(
        "assessment.html",
        pillars=assessment_lib.PILLARS,
        likert=assessment_lib.LIKERT,
    )


@app.route("/assessment/submit", methods=["POST"])
@login_required
@require_csrf
def assessment_submit():
    if not current_user.has_active_subscription:
        return jsonify({"error": "membership required"}), 403

    payload = request.get_json(silent=True) or {}
    answers = payload.get("answers")

    ok, err = assessment_lib.validate_answers(answers)
    if not ok:
        return jsonify(err), 400

    scores = assessment_lib.compute_pillar_scores(answers)
    response = AssessmentResponse(
        user_id=current_user.id,
        submitted_at=datetime.utcnow(),
        answers_json=json.dumps(answers),
        pillar_scores_json=json.dumps(scores),
    )
    db.session.add(response)
    current_user.assessment_complete = True
    db.session.commit()

    return jsonify({"redirect": url_for("assessment_results"), "scores": scores})


@app.route("/assessment/results", methods=["GET"])
@login_required
def assessment_results():
    if not current_user.has_active_subscription:
        return redirect(url_for("pricing"))
    latest = (AssessmentResponse.query
              .filter_by(user_id=current_user.id)
              .order_by(AssessmentResponse.submitted_at.desc())
              .first())
    if not latest:
        return redirect(url_for("assessment"))
    scores = json.loads(latest.pillar_scores_json or "{}")
    return render_template(
        "assessment_results.html",
        response=latest,
        pillars=assessment_lib.PILLARS,
        scores=scores,
    )


@app.route("/assessment/skip", methods=["POST"])
@login_required
@require_csrf
def assessment_skip():
    if not current_user.has_active_subscription:
        return redirect(url_for("pricing"))
    current_user.assessment_complete = True
    db.session.commit()
    return redirect(url_for("onboarding"))


ONBOARDING_STEPS = 5  # photo -> bio -> location -> spaces -> first post


@app.route("/onboarding", methods=["GET"])
@login_required
def onboarding():
    if current_user.onboarding_complete:
        return redirect(url_for("feed"))
    if not current_user.has_active_subscription:
        return redirect(url_for("pricing"))
    try:
        step = int(request.args.get("step", 1))
    except (TypeError, ValueError):
        step = 1
    step = max(1, min(step, ONBOARDING_STEPS))

    spaces = Space.query.order_by(Space.id.asc()).all() if step == 4 else []
    joined_space_ids = (
        [m.space_id for m in SpaceMembership.query.filter_by(user_id=current_user.id).all()]
        if step == 4 else []
    )
    return render_template(
        "onboarding.html",
        step=step,
        total_steps=ONBOARDING_STEPS,
        spaces=spaces,
        joined_space_ids=joined_space_ids,
    )


@app.route("/onboarding", methods=["POST"])
@login_required
@require_csrf
def onboarding_submit():
    if current_user.onboarding_complete:
        return redirect(url_for("feed"))
    try:
        step = int(request.form.get("step", 1))
    except (TypeError, ValueError):
        step = 1
    skip = request.form.get("skip") == "1"

    if step == 1 and not skip:
        if "profile_photo" in request.files:
            f = request.files["profile_photo"]
            if f and f.filename:
                path = save_upload(f)
                if path:
                    current_user.profile_photo = path
                    db.session.commit()
    elif step == 2 and not skip:
        bio = request.form.get("bio", "").strip()
        if bio:
            current_user.bio = bio[:2000]
            db.session.commit()
    elif step == 3 and not skip:
        city = request.form.get("city", "").strip()[:100]
        country = request.form.get("country", "").strip()[:100]
        lat = request.form.get("lat", "").strip()
        lng = request.form.get("lng", "").strip()
        if city:
            current_user.city = city
        if country:
            current_user.country = country
        try:
            if lat and lng:
                current_user.lat = float(lat)
                current_user.lng = float(lng)
        except ValueError:
            pass
        vis = (request.form.get("location_visibility") or "").strip()
        if vis in ("hidden", "city_only", "proximity_visible"):
            current_user.location_visibility = vis
            current_user.show_on_map = (vis != "hidden")
        db.session.commit()
    elif step == 4 and not skip:
        chosen = request.form.getlist("space_ids")
        for sid in chosen[:6]:
            try:
                space_id = int(sid)
            except ValueError:
                continue
            existing = SpaceMembership.query.filter_by(user_id=current_user.id, space_id=space_id).first()
            if not existing:
                db.session.add(SpaceMembership(user_id=current_user.id, space_id=space_id))
        db.session.commit()
    elif step == 5 and not skip:
        content = request.form.get("first_post", "").strip()
        if content:
            post = Post(user_id=current_user.id, content=content[:5000])
            db.session.add(post)
            current_user.add_points(10)
            db.session.commit()

    if current_user.bio and current_user.profile_photo:
        from phase3_routes import _check_item_by_slug
        _check_item_by_slug(current_user.id, "complete-profile")

    next_step = step + 1
    if next_step > ONBOARDING_STEPS:
        current_user.onboarding_complete = True
        current_user.ensure_referral_code()
        db.session.commit()
        flash("Onboarding complete. Welcome to the Society.", "success")
        return redirect(url_for("feed"))
    return redirect(url_for("onboarding", step=next_step))


@app.route("/feed")
@login_required
def feed():
    from sqlalchemy.orm import joinedload, selectinload
    filter_type = request.args.get("filter", "all")
    base = Post.query.options(
        joinedload(Post.author),
        selectinload(Post.likes),
        selectinload(Post.comments),
    )
    if filter_type == "following":
        following_ids = [f.followed_id for f in Follow.query.filter_by(follower_id=current_user.id).all()]
        following_ids.append(current_user.id)
        posts = base.filter(Post.user_id.in_(following_ids), Post.space_id.is_(None)).order_by(Post.created_at.desc()).limit(100).all()
    else:
        posts = base.filter(Post.space_id.is_(None)).order_by(Post.created_at.desc()).limit(100).all()
    member_count = User.query.count()

    # Welcome checklist for sidebar
    checklist_items = ChecklistItem.query.order_by(ChecklistItem.order_index.asc()).all()
    checklist = []
    for item in checklist_items:
        uc = UserChecklist.query.filter_by(user_id=current_user.id, item_id=item.id).first()
        checklist.append({"item": item, "completed": uc.completed if uc else False})
    checklist_done = sum(1 for c in checklist if c["completed"])
    checklist_total = len(checklist)
    checklist_pct = int((checklist_done / checklist_total) * 100) if checklist_total > 0 else 0
    checklist_all_done = checklist_done == checklist_total and checklist_total > 0
    # Sidebar shows up to 5 items, incomplete first.
    sidebar_checklist = sorted(checklist, key=lambda c: (c["completed"], c["item"].order_index))[:5]
    sidebar_overflow = max(0, checklist_total - len(sidebar_checklist))

    focus_composer = request.args.get("focus") == "composer"

    return render_template("feed.html", posts=posts, member_count=member_count, filter_type=filter_type,
                           checklist=checklist, sidebar_checklist=sidebar_checklist,
                           sidebar_overflow=sidebar_overflow,
                           checklist_done=checklist_done, checklist_total=checklist_total,
                           checklist_pct=checklist_pct, checklist_all_done=checklist_all_done,
                           focus_composer=focus_composer)


@app.route("/feed", methods=["POST"])
@login_required
def create_post():
    content = request.form.get("content", "").strip()
    if not content:
        flash("Post cannot be empty.", "error")
        return redirect(url_for("feed"))

    image_path = None
    if "image" in request.files:
        file = request.files["image"]
        if file.filename:
            image_path = save_upload(file)

    post = Post(user_id=current_user.id, content=content, image_path=image_path)
    db.session.add(post)
    current_user.add_points(10)

    # Handle poll creation
    poll_question = request.form.get("poll_question", "").strip()
    poll_options_raw = request.form.getlist("poll_options[]")
    poll_options = [o.strip() for o in poll_options_raw if o.strip()]
    if poll_question and len(poll_options) >= 2:
        db.session.flush()  # Get the post.id
        poll = Poll(post_id=post.id, question=poll_question)
        db.session.add(poll)
        db.session.flush()
        for opt_text in poll_options:
            option = PollOption(poll_id=poll.id, text=opt_text)
            db.session.add(option)

    db.session.commit()

    from phase3_routes import _check_item_by_slug
    _check_item_by_slug(current_user.id, "first-post")

    flash("Post published.", "success")
    return redirect(url_for("feed"))


@app.route("/like/<int:post_id>", methods=["POST"])
@login_required
def toggle_like(post_id):
    post = Post.query.get_or_404(post_id)
    existing = Like.query.filter_by(post_id=post_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        post.author.add_points(-2)
        db.session.commit()
        liked = False
    else:
        like = Like(post_id=post_id, user_id=current_user.id)
        db.session.add(like)
        post.author.add_points(2)
        create_notification(
            post.user_id, "new_like",
            f"{current_user.name} liked your post",
            url_for("feed") + f"#post-{post_id}"
        )
        db.session.commit()
        liked = True
    return jsonify({"liked": liked, "count": post.like_count})


@app.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get("content", "").strip()
    if not content:
        flash("Comment cannot be empty.", "error")
        return redirect(request.referrer or url_for("feed"))

    comment = Comment(post_id=post_id, user_id=current_user.id, content=content)
    db.session.add(comment)
    current_user.add_points(5)
    create_notification(
        post.user_id, "new_comment",
        f"{current_user.name} commented on your post",
        url_for("feed") + f"#post-{post_id}"
    )
    db.session.commit()
    return redirect(request.referrer or url_for("feed"))


@app.route("/post/<int:post_id>", methods=["DELETE"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    # Delete uploaded image if exists
    if post.image_path:
        img_path = os.path.join(app.config["UPLOAD_FOLDER"], os.path.basename(post.image_path))
        if os.path.exists(img_path):
            os.remove(img_path)
    db.session.delete(post)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
@require_csrf
def login():
    if current_user.is_authenticated:
        return redirect(url_for("feed"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            user.update_streak()
            db.session.commit()
            login_user(user, remember=True)
            if not user.has_active_subscription:
                logout_user()
                flash("Your membership is inactive. Rejoin here.", "warning")
                return redirect(url_for("pricing"))
            if not user.onboarding_complete:
                return redirect(url_for("onboarding"))
            return redirect(url_for("feed"))
        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
@limiter.limit("3 per minute", methods=["POST"])
@require_csrf
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("feed"))

    prefilled_email = request.args.get("email", "").strip().lower()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("signup.html", email=email)

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup.html", email=email)

        if len(password) < 10:
            flash("Password must be at least 10 characters.", "error")
            return render_template("signup.html", email=email)

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return render_template("signup.html", email=email)

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        profile_photo = None
        if "profile_photo" in request.files:
            file = request.files["profile_photo"]
            if file.filename:
                profile_photo = save_upload(file)

        user = User(
            name=name,
            email=email,
            password_hash=hashed,
            profile_photo=profile_photo,
            points=0,
            streak_days=1,
            last_login_date=date.today(),
        )
        db.session.add(user)
        db.session.commit()

        # Free signup, no card on file — pure prospect (no trial yet).
        ghl.upsert_contact(email=email, name=name, stage_tag="prospect")

        flash("Account created. Complete your membership to gain access.", "success")
        return redirect(url_for("pricing"))

    return render_template("signup.html", email=prefilled_email)


@app.route("/signup-with-code", methods=["POST"])
@limiter.limit("5 per minute")
@require_csrf
def signup_with_code():
    """Create a fully-active lifetime account from a valid founder code.

    Mirrors the operational pattern of ``admin_grant_lifetime`` (lifetime_access
    flip + active subscription_status + GHL push + lifetime email) but skips
    the admin-only gate and the email-verification step. JSON-in, JSON-out.

    Pairs with ``/validate-code`` (which both share ``_is_founder_code``) and
    the founder-mode branch in ``templates/pricing.html``.
    """
    if current_user.is_authenticated:
        return jsonify({"redirect": url_for("feed")})

    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    code = (data.get("code") or "").strip()

    if not name or not email or not password or not code:
        return jsonify({"error": "All fields are required."}), 400
    if len(password) < 10:
        return jsonify({"error": "Password must be at least 10 characters."}), 400
    if not _is_founder_code(code):
        return jsonify({"error": "Invalid founder code."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists. Please log in."}), 400

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(
        name=name,
        email=email,
        password_hash=hashed,
        points=0,
        streak_days=1,
        last_login_date=date.today(),
        subscription_status="active",
        lifetime_access=True,
        lifetime_qualified_at=datetime.utcnow(),
        email_verified=True,
    )
    user.ensure_referral_code()
    db.session.add(user)
    db.session.commit()

    # GHL push — canonical lifetime-qualified taxonomy (Phase 1).
    ghl.upsert_contact(
        email=email, name=name,
        stage_tag="lifetime-qualified",
        custom_fields=ghl.custom_fields_from_user(user),
    )

    # Welcome email — graceful degrade if RESEND_API_KEY is unset.
    try:
        send_lifetime_unlocked(user)
    except Exception as e:
        app.logger.warning("send_lifetime_unlocked failed (non-fatal): %s", e)

    login_user(user, remember=True)
    return jsonify({"redirect": _post_signup_redirect_url(user)})


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ===== Password reset =====

@app.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per minute", methods=["POST"])
@require_csrf
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            user.password_reset_token = secrets.token_urlsafe(32)
            user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            reset_url = url_for("reset_password", token=user.password_reset_token, _external=True)
            send_password_reset(user, reset_url)
        # Always show same message to prevent email enumeration.
        flash("If that email is registered, a reset link is on its way.", "success")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
@require_csrf
def reset_password(token):
    user = User.query.filter_by(password_reset_token=token).first()
    if not user or not user.password_reset_expires or user.password_reset_expires < datetime.utcnow():
        flash("Reset link is invalid or expired. Request a new one.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < 10:
            flash("Password must be at least 10 characters.", "error")
            return render_template("reset_password.html", token=token)
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html", token=token)
        user.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user.password_reset_token = None
        user.password_reset_expires = None
        db.session.commit()
        flash("Password updated. Sign in with your new password.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


# ===== Email verification =====

def _issue_verify_token(user):
    user.email_verify_token = secrets.token_urlsafe(32)
    user.email_verify_expires = datetime.utcnow() + timedelta(days=7)
    db.session.commit()
    return user.email_verify_token


def send_verification_email(user):
    token = _issue_verify_token(user)
    verify_url = url_for("verify_email", token=token, _external=True)
    send_welcome_verify(user, verify_url)


@app.route("/verify-email/<token>")
def verify_email(token):
    user = User.query.filter_by(email_verify_token=token).first()
    if not user or not user.email_verify_expires or user.email_verify_expires < datetime.utcnow():
        flash("Verification link is invalid or expired.", "error")
        return redirect(url_for("login"))
    user.email_verified = True
    user.email_verify_token = None
    user.email_verify_expires = None
    db.session.commit()
    flash("Email confirmed. Welcome.", "success")
    if current_user.is_authenticated:
        return redirect(url_for("feed"))
    return redirect(url_for("login"))


@app.route("/resend-verification", methods=["POST"])
@login_required
@limiter.limit("3 per hour")
@require_csrf
def resend_verification():
    if current_user.email_verified:
        flash("Email already verified.", "success")
    else:
        send_verification_email(current_user)
        flash("Verification email sent.", "success")
    return redirect(request.referrer or url_for("feed"))


@app.route("/profile/<int:user_id>")
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    posts = Post.query.filter_by(user_id=user_id).order_by(Post.created_at.desc()).all()

    # Phase 7: surface the user's active projects on their profile, filtered
    # by the same visibility tiers the /projects feed uses. Self-view returns
    # all active projects regardless of visibility.
    projects_q = Project.query.filter_by(user_id=user_id, is_active=True)
    if current_user.id != user_id:
        if getattr(current_user, "lifetime_access", False):
            projects_q = projects_q.filter(Project.visibility.in_(["members_only", "brotherhood_only"]))
        elif getattr(current_user, "has_active_subscription", False):
            projects_q = projects_q.filter(Project.visibility == "members_only")
        else:
            projects_q = projects_q.filter(False)
    projects = projects_q.order_by(Project.updated_at.desc()).all()

    return render_template("profile.html", user=user, posts=posts, projects=projects)


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name).strip()
        current_user.bio = request.form.get("bio", "").strip()

        if "profile_photo" in request.files:
            file = request.files["profile_photo"]
            if file.filename:
                photo_path = save_upload(file)
                if photo_path:
                    # Remove old photo
                    if current_user.profile_photo:
                        old_path = os.path.join(
                            app.config["UPLOAD_FOLDER"],
                            os.path.basename(current_user.profile_photo),
                        )
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    current_user.profile_photo = photo_path

        db.session.commit()

        if current_user.bio and current_user.profile_photo:
            from phase3_routes import _check_item_by_slug
            _check_item_by_slug(current_user.id, "complete-profile")

        flash("Profile updated.", "success")
        return redirect(url_for("profile", user_id=current_user.id))

    return render_template("edit_profile.html")


@app.route("/members")
@login_required
def members():
    all_members = User.query.order_by(User.created_at.desc()).all()
    return render_template("members.html", members=all_members)


# ===== LEADERBOARD =====

@app.route("/leaderboard")
@login_required
def leaderboard():
    top_users = User.query.order_by(User.points.desc()).limit(50).all()
    # Find current user rank
    all_ranked = User.query.order_by(User.points.desc()).all()
    my_rank = None
    for i, u in enumerate(all_ranked):
        if u.id == current_user.id:
            my_rank = i + 1
            break
    return render_template("leaderboard.html", top_users=top_users, my_rank=my_rank)


# ===== FOLLOW SYSTEM =====

@app.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def toggle_follow(user_id):
    if user_id == current_user.id:
        return jsonify({"error": "Cannot follow yourself"}), 400

    user = User.query.get_or_404(user_id)
    existing = Follow.query.filter_by(follower_id=current_user.id, followed_id=user_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        following = False
    else:
        follow = Follow(follower_id=current_user.id, followed_id=user_id)
        db.session.add(follow)
        create_notification(
            user_id, "new_follower",
            f"{current_user.name} started following you",
            url_for("profile", user_id=current_user.id)
        )
        db.session.commit()

        follow_count = Follow.query.filter_by(follower_id=current_user.id).count()
        if follow_count >= 3:
            from phase3_routes import _check_item_by_slug
            _check_item_by_slug(current_user.id, "follow-brothers")

        following = True
    return jsonify({
        "following": following,
        "follower_count": user.follower_count,
        "following_count": user.following_count
    })


# ===== SPACES =====

@app.route("/spaces")
@login_required
def spaces():
    all_spaces = Space.query.order_by(Space.created_at.desc()).all()
    return render_template("spaces.html", spaces=all_spaces)


@app.route("/space/<int:space_id>")
@login_required
def space_detail(space_id):
    space = Space.query.get_or_404(space_id)
    posts = Post.query.filter_by(space_id=space_id).order_by(Post.created_at.desc()).all()
    return render_template("space_detail.html", space=space, posts=posts)


@app.route("/space/create", methods=["GET", "POST"])
@login_required
def create_space():
    if not current_user.is_admin:
        flash("Only admins can create spaces.", "error")
        return redirect(url_for("spaces"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Space name is required.", "error")
            return render_template("create_space.html")

        cover_image = None
        if "cover_image" in request.files:
            file = request.files["cover_image"]
            if file.filename:
                cover_image = save_upload(file)

        space = Space(name=name, description=description, cover_image=cover_image, created_by=current_user.id)
        db.session.add(space)
        db.session.flush()
        # Auto-join creator as admin
        membership = SpaceMembership(user_id=current_user.id, space_id=space.id, role="admin")
        db.session.add(membership)
        db.session.commit()
        flash(f"Space '{name}' created.", "success")
        return redirect(url_for("space_detail", space_id=space.id))

    return render_template("create_space.html")


@app.route("/space/<int:space_id>/join", methods=["POST"])
@login_required
def join_space(space_id):
    space = Space.query.get_or_404(space_id)
    if space.is_member(current_user):
        flash("You're already a member.", "error")
        return redirect(url_for("space_detail", space_id=space_id))
    membership = SpaceMembership(user_id=current_user.id, space_id=space_id)
    db.session.add(membership)
    db.session.commit()

    from phase3_routes import _check_item_by_slug
    _check_item_by_slug(current_user.id, "join-space")

    flash(f"Joined {space.name}.", "success")
    return redirect(url_for("space_detail", space_id=space_id))


@app.route("/space/<int:space_id>/leave", methods=["POST"])
@login_required
def leave_space(space_id):
    space = Space.query.get_or_404(space_id)
    membership = SpaceMembership.query.filter_by(user_id=current_user.id, space_id=space_id).first()
    if membership:
        db.session.delete(membership)
        db.session.commit()
        flash(f"Left {space.name}.", "success")
    return redirect(url_for("spaces"))


@app.route("/space/<int:space_id>/post", methods=["POST"])
@login_required
def create_space_post(space_id):
    space = Space.query.get_or_404(space_id)
    if not space.is_member(current_user):
        flash("Join the space to post.", "error")
        return redirect(url_for("space_detail", space_id=space_id))

    content = request.form.get("content", "").strip()
    if not content:
        flash("Post cannot be empty.", "error")
        return redirect(url_for("space_detail", space_id=space_id))

    image_path = None
    if "image" in request.files:
        file = request.files["image"]
        if file.filename:
            image_path = save_upload(file)

    post = Post(user_id=current_user.id, content=content, image_path=image_path, space_id=space_id)
    db.session.add(post)
    current_user.add_points(10)

    # Notify space members
    for m in space.memberships:
        if m.user_id != current_user.id:
            create_notification(
                m.user_id, "new_post_in_space",
                f"{current_user.name} posted in {space.name}",
                url_for("space_detail", space_id=space_id)
            )

    # Handle poll creation
    poll_question = request.form.get("poll_question", "").strip()
    poll_options_raw = request.form.getlist("poll_options[]")
    poll_options = [o.strip() for o in poll_options_raw if o.strip()]
    if poll_question and len(poll_options) >= 2:
        db.session.flush()
        poll = Poll(post_id=post.id, question=poll_question)
        db.session.add(poll)
        db.session.flush()
        for opt_text in poll_options:
            option = PollOption(poll_id=poll.id, text=opt_text)
            db.session.add(option)

    db.session.commit()
    flash("Post published.", "success")
    return redirect(url_for("space_detail", space_id=space_id))


# ===== NOTIFICATIONS =====

@app.route("/notifications")
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return render_template("notifications.html", notifications=notifs)


@app.route("/notifications/read", methods=["POST"])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"success": True})


# ===== NOTIFICATION API ENDPOINTS =====

@app.route("/api/notifications/unread-count")
@login_required
def api_unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"count": count})


@app.route("/api/notifications/recent")
@login_required
def api_recent_notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(8).all()
    result = []
    for n in notifs:
        result.append({
            "id": n.id,
            "type": n.type,
            "message": n.message,
            "link": n.link,
            "is_read": n.is_read,
            "time_ago": n.time_ago,
        })
    return jsonify({"notifications": result})


@app.route("/notifications/mark-read", methods=["POST"])
@login_required
def mark_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"success": True})


# ===== POLLS =====

@app.route("/poll/vote/<int:option_id>", methods=["POST"])
@login_required
def vote_poll(option_id):
    option = PollOption.query.get_or_404(option_id)
    poll = option.poll
    # Check if user already voted on this poll
    if poll.user_voted(current_user):
        return jsonify({"error": "Already voted"}), 400
    vote = PollVote(option_id=option_id, user_id=current_user.id)
    db.session.add(vote)
    db.session.commit()
    # Return updated results
    total = poll.total_votes
    results = []
    for opt in poll.options:
        results.append({
            "id": opt.id,
            "text": opt.text,
            "votes": opt.vote_count,
            "percentage": opt.percentage(total)
        })
    return jsonify({"success": True, "total": total, "results": results})


# ===== STRIPE / SUBSCRIPTION =====

@app.route("/pricing")
def pricing():
    if current_user.is_authenticated and current_user.has_active_subscription:
        return render_template("pricing.html", stripe_key=STRIPE_PUBLISHABLE_KEY)
    return render_template("pricing.html", stripe_key=STRIPE_PUBLISHABLE_KEY)


def _valid_founder_codes():
    """Single source of truth for founder-code values. Reads env once per call.

    Supports comma-separated multiple codes via ``FOUNDER_CODES`` (or the legacy
    singular ``FOUNDER_CODE``). Default ``ABMC2026`` mirrors prior behavior.
    """
    raw = os.environ.get("FOUNDER_CODES") or os.environ.get("FOUNDER_CODE") or "ABMC2026"
    return [c.strip() for c in raw.split(",") if c.strip()]


def _is_founder_code(code):
    """Returns True iff the (stripped) string matches a current founder code."""
    if not code:
        return False
    return code.strip() in _valid_founder_codes()


@app.route("/validate-code", methods=["POST"])
def validate_code():
    code = (request.json or {}).get("code", "") if request.is_json else request.form.get("code", "")
    if _is_founder_code(code):
        return jsonify({"valid": True})
    return jsonify({"valid": False})


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    try:
        # Check if Stripe is actually configured
        stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
        if not stripe_key or "REPLACE" in stripe_key or "sk_test_placeholder" in stripe_key:
            return jsonify({"error": "Payment is not configured yet. Use a founder code to join."}), 400

        email = request.json.get("email", "").strip().lower() if request.is_json else ""
        if not email:
            return jsonify({"error": "Email is required."}), 400

        # Check if a user already exists with this email
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"error": "An account with this email already exists. Please log in."}), 400

        # Create Stripe customer with email
        customer = stripe.Customer.create(
            email=email,
            metadata={"signup_email": email},
        )

        session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            allow_promotion_codes=True,
            success_url=request.host_url.rstrip("/") + url_for("subscription_success") + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url.rstrip("/") + url_for("pricing"),
            metadata={"email": email},
        )
        return jsonify({"checkout_url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/subscription/success", methods=["GET", "POST"])
@require_csrf
def subscription_success():
    session_id = request.args.get("session_id")
    if not session_id:
        return redirect(url_for("pricing"))

    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        sub = stripe.Subscription.retrieve(stripe_session.subscription)
        email = stripe_session.metadata.get("email") or (stripe_session.customer_details.email if stripe_session.customer_details else "")
        email = (email or "").strip().lower()
        stripe_customer_id = stripe_session.customer
        stripe_subscription_id = sub.id
        period_end = datetime.utcfromtimestamp(sub.current_period_end)
    except Exception:
        flash("Could not verify your payment. Please contact support.", "error")
        return redirect(url_for("pricing"))

    # If user already exists with this email, log them in (handles page refresh).
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        # Backfill stripe info if missing (webhook may have arrived first).
        if not existing_user.stripe_customer_id:
            existing_user.stripe_customer_id = stripe_customer_id
            existing_user.stripe_subscription_id = stripe_subscription_id
            existing_user.subscription_status = "active"
            existing_user.subscription_current_period_end = period_end
            db.session.commit()
        login_user(existing_user, remember=True)
        return _post_signup_redirect(existing_user)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not password:
            flash("Name and password are required.", "error")
            return render_template("signup.html", email=email, session_id=session_id, stripe_mode=True)
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup.html", email=email, session_id=session_id, stripe_mode=True)
        if len(password) < 10:
            flash("Password must be at least 10 characters.", "error")
            return render_template("signup.html", email=email, session_id=session_id, stripe_mode=True)

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        profile_photo = None
        if "profile_photo" in request.files:
            f = request.files["profile_photo"]
            if f.filename:
                profile_photo = save_upload(f)

        user = User(
            name=name,
            email=email,
            password_hash=hashed,
            profile_photo=profile_photo,
            points=0,
            streak_days=1,
            last_login_date=date.today(),
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            subscription_status="active",
            subscription_current_period_end=period_end,
        )
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)

        # Trigger welcome + verify email
        send_verification_email(user)

        # No trial — paid signups go straight to active-member on day 1.
        # The webhook's invoice.payment_succeeded handler will idempotently
        # re-tag with the same value once Stripe processes the first invoice.
        ghl.upsert_contact(
            email=email, name=name,
            stage_tag="active-member",
            custom_fields=ghl.custom_fields_from_user(user),
        )
        flash("Welcome to the Society. Check your email to confirm.", "success")
        return _post_signup_redirect(user)

    return render_template("signup.html", email=email, session_id=session_id, stripe_mode=True)


# Referral-based lifetime: a member qualifies when 3 of their referrals
# each complete 6 successful payments.
PAYMENTS_PER_REFERRAL_QUALIFICATION = 6
QUALIFIED_REFERRALS_FOR_LIFETIME = 3


@app.route("/webhook/stripe", methods=["POST"])
@csrf.exempt
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return jsonify({"error": "Invalid signature"}), 400

    # Idempotency: skip events we've already processed.
    event_id = event.get("id")
    if event_id and StripeEvent.query.filter_by(stripe_event_id=event_id).first():
        return jsonify({"status": "duplicate"})

    event_type = event["type"]
    data = event["data"]["object"]

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(data)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data)
        elif event_type == "invoice.payment_succeeded":
            _handle_payment_succeeded(data)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(data)
    finally:
        if event_id:
            db.session.add(StripeEvent(stripe_event_id=event_id, event_type=event_type))
            db.session.commit()

    return jsonify({"status": "ok"})


def _handle_checkout_completed(data):
    """Backfill user's stripe IDs if they reached this state via webhook before /success."""
    customer_id = data.get("customer")
    email = (data.get("customer_details") or {}).get("email") or (data.get("metadata") or {}).get("email")
    if not customer_id or not email:
        return
    user = User.query.filter_by(email=email.strip().lower()).first()
    if user and not user.stripe_customer_id:
        user.stripe_customer_id = customer_id
        user.stripe_subscription_id = data.get("subscription")
        user.subscription_status = "active"
        db.session.commit()


def _handle_subscription_updated(data):
    user = User.query.filter_by(stripe_subscription_id=data["id"]).first()
    if not user:
        return
    if user.lifetime_access:
        # Don't overwrite lifetime status with downstream sub events.
        return
    user.subscription_status = "active" if data["status"] == "active" else data["status"]
    if data.get("current_period_end"):
        user.subscription_current_period_end = datetime.utcfromtimestamp(data["current_period_end"])
    db.session.commit()


def _handle_subscription_deleted(data):
    user = User.query.filter_by(stripe_subscription_id=data["id"]).first()
    if not user:
        return
    if user.lifetime_access:
        # Lifetime member's sub was canceled (by us, after 3 payments) — don't downgrade.
        return
    user.subscription_status = "canceled"
    db.session.commit()
    # Trial-cancelled (never charged) is a different audience from member-cancelled
    # (paid at least once). Different win-back messaging in GHL workflows.
    cancel_tag = "trial-cancelled" if (user.payments_made_count or 0) == 0 else "cancelled"
    ghl.upsert_contact(
        email=user.email, name=user.name,
        stage_tag=cancel_tag,
        custom_fields=ghl.custom_fields_from_user(user),
    )


def _handle_payment_succeeded(data):
    """Process a successful $99 payment.

    Counts toward this user's payments_made_count. When their count hits 6,
    their referrer (if any) gets +1 to qualified_referrals_count. When the
    referrer's count hits 3, the referrer gets lifetime access.
    """
    customer_id = data.get("customer")
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return
    if user.lifetime_access:
        return  # Lifetime members shouldn't be billed; safety net.

    user.payments_made_count = (user.payments_made_count or 0) + 1
    user.subscription_status = "active"

    # Did this payment cause the user to *qualify* for their referrer?
    just_qualified_for_referrer = (
        user.payments_made_count == PAYMENTS_PER_REFERRAL_QUALIFICATION
        and user.referred_by is not None
    )

    referrer_unlocked_lifetime = False
    referrer = None
    if just_qualified_for_referrer:
        referrer = User.query.get(user.referred_by)
        if referrer and not referrer.lifetime_access:
            referrer.qualified_referrals_count = (referrer.qualified_referrals_count or 0) + 1
            if referrer.qualified_referrals_count >= QUALIFIED_REFERRALS_FOR_LIFETIME:
                referrer.lifetime_access = True
                referrer.lifetime_qualified_at = datetime.utcnow()
                referrer.subscription_status = "active"
                referrer_unlocked_lifetime = True
                if referrer.stripe_subscription_id:
                    try:
                        stripe.Subscription.cancel(referrer.stripe_subscription_id)
                    except Exception as e:
                        print(f"[STRIPE] Failed to cancel referrer sub {referrer.stripe_subscription_id}: {e}")

    db.session.commit()

    # Receipt to the paying user
    amount = data.get("amount_paid", 0) or 0
    send_payment_succeeded(user, amount, user.payments_made_count, lifetime_unlocked=False)

    # Notify referrer of progress / qualification
    if referrer:
        try:
            from email_send import send_referral_progress
            send_referral_progress(
                referrer=referrer,
                referee=user,
                qualified_count=referrer.qualified_referrals_count,
                threshold=QUALIFIED_REFERRALS_FOR_LIFETIME,
            )
        except Exception as e:
            print(f"[EMAIL] referral progress failed: {e}")

    # Phase 1: keep custom fields fresh on every successful payment, even when
    # the user did not just unlock their referrer's lifetime. Phase 2 widens
    # this to checkout.completed / sub.updated / payment_failed.
    ghl.upsert_contact(
        email=user.email, name=user.name,
        stage_tag="active-member",
        custom_fields=ghl.custom_fields_from_user(user),
    )

    if referrer_unlocked_lifetime:
        send_lifetime_unlocked(referrer)
        ghl.upsert_contact(
            email=referrer.email, name=referrer.name,
            stage_tag="lifetime-qualified",
            custom_fields=ghl.custom_fields_from_user(referrer),
        )


def _handle_payment_failed(data):
    customer_id = data.get("customer")
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user or user.lifetime_access:
        return
    user.subscription_status = "past_due"
    db.session.commit()
    update_url = request.host_url.rstrip("/") + url_for("billing_portal")
    send_payment_failed(user, update_url)


@app.route("/billing-portal", methods=["POST"])
@login_required
def billing_portal():
    if not current_user.stripe_customer_id:
        flash("No billing account found.", "error")
        return redirect(url_for("pricing"))
    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=request.host_url.rstrip("/") + url_for("feed"),
        )
        return redirect(session.url)
    except Exception as e:
        flash(f"Could not open billing portal: {e}", "error")
        return redirect(url_for("pricing"))


# ===== ADMIN PANEL =====

@app.route("/admin")
@admin_required
def admin_panel():
    q = request.args.get("q", "").strip()
    members_q = User.query
    if q:
        like = f"%{q}%"
        members_q = members_q.filter((User.email.ilike(like)) | (User.name.ilike(like)))
    members = members_q.order_by(User.created_at.desc()).limit(200).all()

    stats = {
        "total_members": User.query.count(),
        "active_subs": User.query.filter_by(subscription_status="active", lifetime_access=False).count(),
        "lifetime": User.query.filter_by(lifetime_access=True).count(),
        "past_due": User.query.filter_by(subscription_status="past_due").count(),
        "canceled": User.query.filter_by(subscription_status="canceled").count(),
        "mrr_cents": User.query.filter_by(subscription_status="active", lifetime_access=False).count() * 9900,
        "total_posts": Post.query.count(),
        "total_spaces": Space.query.count(),
    }
    return render_template("admin.html", members=members, stats=stats, q=q)


@app.route("/admin/member/<int:user_id>")
@admin_required
def admin_member_detail(user_id):
    user = User.query.get_or_404(user_id)
    stripe_events = []
    if user.stripe_customer_id and "placeholder" not in (STRIPE_SECRET_KEY or "").lower():
        try:
            invoices = stripe.Invoice.list(customer=user.stripe_customer_id, limit=20)
            stripe_events = [
                {
                    "id": inv.id,
                    "amount": inv.amount_paid / 100.0,
                    "status": inv.status,
                    "created": datetime.utcfromtimestamp(inv.created),
                    "hosted_url": inv.hosted_invoice_url,
                }
                for inv in invoices.auto_paging_iter()
            ]
        except Exception as e:
            print(f"[ADMIN] Stripe lookup failed: {e}")
    return render_template("admin_member.html", user=user, stripe_events=stripe_events)


@app.route("/admin/toggle-admin/<int:user_id>", methods=["POST"])
@admin_required
@require_csrf
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Cannot change your own admin status.", "error")
        return redirect(url_for("admin_panel"))
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(f"{'Granted' if user.is_admin else 'Revoked'} admin for {user.name}.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/toggle-subscription/<int:user_id>", methods=["POST"])
@admin_required
@require_csrf
def toggle_subscription(user_id):
    user = User.query.get_or_404(user_id)
    user.subscription_status = "inactive" if user.subscription_status == "active" else "active"
    db.session.commit()
    flash(f"Subscription set to {user.subscription_status} for {user.name}.", "success")
    return redirect(request.referrer or url_for("admin_panel"))


@app.route("/admin/grant-lifetime/<int:user_id>", methods=["POST"])
@admin_required
@require_csrf
def admin_grant_lifetime(user_id):
    user = User.query.get_or_404(user_id)
    user.lifetime_access = True
    user.subscription_status = "active"
    db.session.commit()
    # If they have an active Stripe sub, cancel it (no more billing).
    if user.stripe_subscription_id and "placeholder" not in (STRIPE_SECRET_KEY or "").lower():
        try:
            stripe.Subscription.cancel(user.stripe_subscription_id)
        except Exception as e:
            flash(f"Lifetime granted, but Stripe cancel failed: {e}", "warning")
    flash(f"Lifetime access granted to {user.name}.", "success")
    return redirect(url_for("admin_member_detail", user_id=user.id))


@app.route("/admin/revoke-lifetime/<int:user_id>", methods=["POST"])
@admin_required
@require_csrf
def admin_revoke_lifetime(user_id):
    user = User.query.get_or_404(user_id)
    user.lifetime_access = False
    db.session.commit()
    flash(f"Lifetime access revoked for {user.name}.", "success")
    return redirect(url_for("admin_member_detail", user_id=user.id))


@app.route("/admin/refund-last/<int:user_id>", methods=["POST"])
@admin_required
@require_csrf
def admin_refund_last(user_id):
    user = User.query.get_or_404(user_id)
    if not user.stripe_customer_id:
        flash("No Stripe customer.", "error")
        return redirect(url_for("admin_member_detail", user_id=user.id))
    try:
        charges = stripe.Charge.list(customer=user.stripe_customer_id, limit=1)
        if not charges.data:
            flash("No charges to refund.", "error")
            return redirect(url_for("admin_member_detail", user_id=user.id))
        last = charges.data[0]
        stripe.Refund.create(charge=last.id)
        flash(f"Refunded ${last.amount/100:.2f} to {user.name}.", "success")
    except Exception as e:
        flash(f"Refund failed: {e}", "error")
    return redirect(url_for("admin_member_detail", user_id=user.id))


@app.route("/admin/comp-month/<int:user_id>", methods=["POST"])
@admin_required
@require_csrf
def admin_comp_month(user_id):
    user = User.query.get_or_404(user_id)
    user.subscription_status = "active"
    user.subscription_current_period_end = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    flash(f"Comped 30 days for {user.name}.", "success")
    return redirect(url_for("admin_member_detail", user_id=user.id))


@app.route("/admin/ghl/health")
@admin_required
def admin_ghl_health():
    """Surface GHL connectivity status. Production writes fail silently by
    design (daemon thread + try/except), so this is the on-demand probe."""
    result = ghl.health_check()
    if request.args.get("format") == "json":
        return jsonify(result)
    return render_template("admin_ghl_health.html", result=result)


# ===== THE VAULT (lessons alias) =====

@app.route("/learn")
@login_required
def learn():
    return redirect(url_for("phase3.lessons"))


# ===== CONTEXT PROCESSOR =====

@app.context_processor
def inject_globals():
    return {
        "stripe_publishable_key": STRIPE_PUBLISHABLE_KEY,
    }


# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('errors/500.html'), 500


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
