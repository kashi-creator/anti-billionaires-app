import os
import uuid
import json
import threading
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import bcrypt
import stripe
import requests
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
    Availability, CallBooking, Activity,
)
from phase3_routes import phase3, seed_checklist
from features_routes import features, seed_badges, check_and_award_badges

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "abmc-dev-secret-key-change-in-prod")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///abmc.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")

# Stripe config
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_placeholder")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "price_placeholder")
stripe.api_key = STRIPE_SECRET_KEY

# GHL config
GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION_ID = os.environ.get("GHL_LOCATION_ID", "")

# Fix for Railway PostgreSQL URL
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace(
        "postgres://", "postgresql://", 1
    )

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "pricing"
app.register_blueprint(phase3)
app.register_blueprint(features)

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


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


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

def ghl_upsert_contact(email, name, tags=None, phone=None):
    """Upsert a contact in GoHighLevel. Non-blocking via threading."""
    if not GHL_API_KEY or not GHL_LOCATION_ID:
        return

    def _do_upsert():
        try:
            headers = {
                "Authorization": f"Bearer {GHL_API_KEY}",
                "Content-Type": "application/json",
                "Version": "2021-07-28",
            }
            payload = {
                "email": email,
                "name": name,
                "locationId": GHL_LOCATION_ID,
            }
            if tags:
                payload["tags"] = tags
            if phone:
                payload["phone"] = phone
            requests.post(
                "https://services.leadconnectorhq.com/contacts/upsert",
                headers=headers,
                json=payload,
                timeout=10,
            )
        except Exception:
            pass  # Non-blocking, fail silently

    t = threading.Thread(target=_do_upsert, daemon=True)
    t.start()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create tables on startup
with app.app_context():
    db.create_all()
    seed_checklist()
    # Migrate existing tables: add new columns if they don't exist
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    user_columns = [c["name"] for c in inspector.get_columns("user")]
    if "points" not in user_columns:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE user ADD COLUMN points INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE user ADD COLUMN streak_days INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE user ADD COLUMN last_login_date DATE"))
            conn.commit()
    # Stripe columns migration
    if "stripe_customer_id" not in user_columns:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE user ADD COLUMN stripe_customer_id VARCHAR(100)"))
            conn.execute(text("ALTER TABLE user ADD COLUMN stripe_subscription_id VARCHAR(100)"))
            conn.execute(text("ALTER TABLE user ADD COLUMN subscription_status VARCHAR(30) DEFAULT 'inactive'"))
            conn.execute(text("ALTER TABLE user ADD COLUMN subscription_current_period_end DATETIME"))
            conn.commit()
    # Add space_id to post if missing
    post_columns = [c["name"] for c in inspector.get_columns("post")]
    if "space_id" not in post_columns:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE post ADD COLUMN space_id INTEGER"))
            conn.commit()
    # New User columns migration
    new_user_cols = {
        "referral_code": "VARCHAR(12)",
        "referred_by": "INTEGER",
        "city": "VARCHAR(100)",
        "country": "VARCHAR(100)",
        "lat": "FLOAT",
        "lng": "FLOAT",
        "show_on_map": "BOOLEAN DEFAULT 1",
        "bookings_enabled": "BOOLEAN DEFAULT 0",
        "default_meeting_url": "VARCHAR(500)",
        "has_seen_welcome_video": "BOOLEAN DEFAULT 0",
        "email_digest_opt_out": "BOOLEAN DEFAULT 0",
    }
    for col_name, col_type in new_user_cols.items():
        if col_name not in user_columns:
            try:
                with db.engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
            except Exception:
                pass
    seed_badges()


# --- Seed spaces and events ---
@app.route("/seed-content/<secret>")
def seed_content(secret):
    if secret != "abmc2026seed":
        abort(404)
    from datetime import timedelta
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        return "No admin user found."
    spaces_data = [
        ("The Vault", "Exclusive inner circle for high-level strategy, deal flow, and confidential discussions.", "space-the-vault.png"),
        ("Business Strategy Room", "Where moves are planned. Strategic discussions on scaling, acquisitions, and partnerships.", "space-business-strategy.png"),
        ("Networking Lounge", "Connect with other members. Introductions, collaborations, and relationship building.", "space-networking-lounge.png"),
        ("Investment Club", "Deal sharing, market analysis, crypto, real estate, and alternative investments.", "space-investment-club.png"),
        ("Wellness & Health", "Optimize body and mind. Peptides, HRT, breathwork, meditation, fitness, longevity.", "space-wellness-health.png"),
        ("Creator's Corner", "Content creation, brand building, social media strategy, digital media production.", "space-creators-corner.png"),
    ]
    created = 0
    for name, desc, img in spaces_data:
        if not Space.query.filter_by(name=name).first():
            db.session.add(Space(name=name, description=desc, cover_image=img, created_by=admin.id))
            created += 1
    events_data = [
        ("Weekly Mastermind Call", "Weekly group call - wins, challenges, hot seat format.", 3, "7:00 PM EST", "Zoom"),
        ("Monthly Networking Mixer", "In-person networking in St. Pete. Drinks provided.", 14, "6:30 PM EST", "St. Petersburg, FL"),
        ("Guest Speaker: AI Automation", "Leveraging AI agents for business automation. Live demo.", 7, "8:00 PM EST", "Zoom"),
        ("Deal Flow Friday", "Members present investment opportunities. Pitch format with Q&A.", 5, "12:00 PM EST", "Zoom"),
        ("Wellness Workshop: Peptides", "Deep dive into peptide therapy and longevity protocols.", 10, "7:30 PM EST", "Zoom"),
    ]
    ev_created = 0
    for title, desc, days, t, loc in events_data:
        if not Event.query.filter_by(title=title).first():
            db.session.add(Event(title=title, description=desc, date=(datetime.utcnow() + timedelta(days=days)).date(), time=t, location=loc, host_id=admin.id))
            ev_created += 1
    db.session.commit()
    return f"Seeded {created} spaces and {ev_created} events."

# --- One-time reset (remove after use) ---
@app.route("/reset-pwd/<secret>")
def reset_pwd(secret):
    if secret != "abmc2026reset":
        abort(404)
    user = User.query.filter_by(email="thebreathcoachschool@gmail.com").first()
    if user:
        user.password_hash = bcrypt.hashpw("Swagswag1!".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user.is_admin = True
        user.subscription_status = "active"
        db.session.commit()
        return "Done. Password set and admin activated. Go login."
    return "User not found."

# --- Routes ---

@app.route("/")
def index():
    if current_user.is_authenticated and current_user.has_active_subscription:
        return redirect(url_for("feed"))
    return redirect(url_for("pricing"))


@app.route("/feed")
@login_required
def feed():
    filter_type = request.args.get("filter", "all")
    if filter_type == "following":
        following_ids = [f.followed_id for f in Follow.query.filter_by(follower_id=current_user.id).all()]
        following_ids.append(current_user.id)  # Include own posts
        posts = Post.query.filter(Post.user_id.in_(following_ids), Post.space_id.is_(None)).order_by(Post.created_at.desc()).all()
    else:
        posts = Post.query.filter(Post.space_id.is_(None)).order_by(Post.created_at.desc()).all()
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

    return render_template("feed.html", posts=posts, member_count=member_count, filter_type=filter_type,
                           checklist=checklist, checklist_done=checklist_done, checklist_total=checklist_total,
                           checklist_pct=checklist_pct, checklist_all_done=checklist_all_done)


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

    # Auto-check "Make your first post" checklist item
    from phase3_routes import _auto_check_item
    _auto_check_item(current_user.id, "first post")

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
            login_user(user)
            if user.subscription_status != "active" and not user.is_admin:
                logout_user()
                flash("Your membership is inactive. Rejoin here.", "warning")
                return redirect(url_for("pricing"))
            return redirect(url_for("feed"))
        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("feed"))

    # Only accessible via founder code or Stripe success
    is_founder = request.args.get("founder") == "true"
    prefilled_email = request.args.get("email", "").strip().lower()

    if not is_founder:
        # Regular visitors who hit /signup directly go to pricing
        return redirect(url_for("pricing"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("signup.html", email=email, founder_mode=True)

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup.html", email=email, founder_mode=True)

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup.html", email=email, founder_mode=True)

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return render_template("signup.html", email=email, founder_mode=True)

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
            subscription_status="active",
            is_admin=True,
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)

        # GHL: tag Founder
        ghl_upsert_contact(email, name, tags=["Founder", "ABMC"])

        flash("Welcome to the club, Founder.", "success")
        return redirect(url_for("feed"))

    return render_template("signup.html", email=prefilled_email, founder_mode=True)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/profile/<int:user_id>")
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    posts = Post.query.filter_by(user_id=user_id).order_by(Post.created_at.desc()).all()
    return render_template("profile.html", user=user, posts=posts)


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

        # Auto-check "Complete your profile" checklist
        if current_user.bio and current_user.profile_photo:
            from phase3_routes import _auto_check_item
            _auto_check_item(current_user.id, "Complete your profile")

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

        # Auto-check "Follow 3 members" checklist
        follow_count = Follow.query.filter_by(follower_id=current_user.id).count()
        if follow_count >= 3:
            from phase3_routes import _auto_check_item
            _auto_check_item(current_user.id, "Follow")

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

    # Auto-check "Join a Space" checklist
    from phase3_routes import _auto_check_item
    _auto_check_item(current_user.id, "Join a Space")

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


@app.route("/validate-code", methods=["POST"])
def validate_code():
    code = request.json.get("code", "")
    founder_code = os.environ.get("FOUNDER_CODE", "ABMC2026")
    if code == founder_code:
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
            success_url=request.host_url.rstrip("/") + url_for("subscription_success") + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url.rstrip("/") + url_for("pricing"),
            metadata={"email": email},
        )
        return jsonify({"checkout_url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/subscription/success", methods=["GET", "POST"])
def subscription_success():
    session_id = request.args.get("session_id")
    if not session_id:
        return redirect(url_for("pricing"))

    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        sub = stripe.Subscription.retrieve(stripe_session.subscription)
        email = stripe_session.metadata.get("email", stripe_session.customer_details.email if stripe_session.customer_details else "")
        stripe_customer_id = stripe_session.customer
        stripe_subscription_id = sub.id
        period_end = datetime.utcfromtimestamp(sub.current_period_end)
    except Exception:
        flash("Could not verify your payment. Please contact support.", "error")
        return redirect(url_for("pricing"))

    # If user already exists with this email (e.g. page refresh after account creation), log them in
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        login_user(existing_user)
        return redirect(url_for("feed"))

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

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup.html", email=email, session_id=session_id, stripe_mode=True)

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
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            subscription_status="active",
            subscription_current_period_end=period_end,
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)

        # GHL: tag Paid Member
        ghl_upsert_contact(email, name, tags=["Paid Member", "ABMC"])

        flash("Welcome to the inner circle! Your membership is now active.", "success")
        return redirect(url_for("feed"))

    # GET: show account creation form
    return render_template("signup.html", email=email, session_id=session_id, stripe_mode=True)


@app.route("/webhook/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "customer.subscription.updated":
        sub_id = data["id"]
        user = User.query.filter_by(stripe_subscription_id=sub_id).first()
        if user:
            status = data["status"]
            user.subscription_status = "active" if status == "active" else status
            if data.get("current_period_end"):
                user.subscription_current_period_end = datetime.utcfromtimestamp(data["current_period_end"])
            db.session.commit()

    elif event_type == "customer.subscription.deleted":
        sub_id = data["id"]
        user = User.query.filter_by(stripe_subscription_id=sub_id).first()
        if user:
            user.subscription_status = "canceled"
            db.session.commit()
            # GHL: tag Churned
            ghl_upsert_contact(user.email, user.name, tags=["Churned", "ABMC"])

    elif event_type == "invoice.payment_succeeded":
        customer_id = data.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.subscription_status = "active"
            db.session.commit()

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.subscription_status = "past_due"
            db.session.commit()

    return jsonify({"status": "ok"})


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
    total_members = User.query.count()
    total_subscribers = User.query.filter_by(subscription_status="active").count()
    total_posts = Post.query.count()
    total_events = Event.query.count()
    total_spaces = Space.query.count()
    total_courses = Course.query.count()
    members = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin.html",
                           total_members=total_members,
                           total_subscribers=total_subscribers,
                           total_posts=total_posts,
                           total_events=total_events,
                           total_spaces=total_spaces,
                           total_courses=total_courses,
                           members=members)


@app.route("/admin/toggle-admin/<int:user_id>", methods=["POST"])
@admin_required
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
def toggle_subscription(user_id):
    user = User.query.get_or_404(user_id)
    if user.subscription_status == "active":
        user.subscription_status = "inactive"
    else:
        user.subscription_status = "active"
    db.session.commit()
    flash(f"Subscription {'activated' if user.subscription_status == 'active' else 'deactivated'} for {user.name}.", "success")
    return redirect(url_for("admin_panel"))


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
    app.run(debug=True, port=5000)
