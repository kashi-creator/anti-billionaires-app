from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
import secrets

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text, default="")
    profile_photo = db.Column(db.String(300), default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    # Points & Streaks
    points = db.Column(db.Integer, default=0)
    streak_days = db.Column(db.Integer, default=0)
    last_login_date = db.Column(db.Date, default=None)

    # Stripe Subscription
    stripe_customer_id = db.Column(db.String(100), default=None)
    stripe_subscription_id = db.Column(db.String(100), default=None)
    subscription_status = db.Column(db.String(30), default="inactive")
    subscription_current_period_end = db.Column(db.DateTime, default=None)

    # Referral
    referral_code = db.Column(db.String(12), unique=True, default=None)
    referred_by = db.Column(db.Integer, db.ForeignKey("user.id"), default=None)

    # Location / Map
    city = db.Column(db.String(100), default=None)
    country = db.Column(db.String(100), default=None)
    lat = db.Column(db.Float, default=None)
    lng = db.Column(db.Float, default=None)
    show_on_map = db.Column(db.Boolean, default=True)

    # Booking
    bookings_enabled = db.Column(db.Boolean, default=False)
    default_meeting_url = db.Column(db.String(500), default=None)

    # Preferences
    has_seen_welcome_video = db.Column(db.Boolean, default=False)
    email_digest_opt_out = db.Column(db.Boolean, default=False)

    posts = db.relationship("Post", backref="author", lazy=True, cascade="all, delete-orphan",
                            foreign_keys="Post.user_id")
    comments = db.relationship("Comment", backref="author", lazy=True, cascade="all, delete-orphan")
    likes = db.relationship("Like", backref="user", lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy=True, cascade="all, delete-orphan")
    poll_votes = db.relationship("PollVote", backref="user", lazy=True, cascade="all, delete-orphan")

    @property
    def follower_count(self):
        return Follow.query.filter_by(followed_id=self.id).count()

    @property
    def following_count(self):
        return Follow.query.filter_by(follower_id=self.id).count()

    def is_following(self, user):
        return Follow.query.filter_by(follower_id=self.id, followed_id=user.id).first() is not None

    def is_followed_by(self, user):
        return Follow.query.filter_by(follower_id=user.id, followed_id=self.id).first() is not None

    @property
    def unread_notification_count(self):
        return Notification.query.filter_by(user_id=self.id, is_read=False).count()

    def update_streak(self):
        """Update login streak. Call on each login."""
        today = date.today()
        if self.last_login_date is None:
            self.streak_days = 1
            self.last_login_date = today
            self.points = (self.points or 0) + 5
            return
        delta = (today - self.last_login_date).days
        if delta == 0:
            return  # Already logged in today
        elif delta == 1:
            self.streak_days = (self.streak_days or 0) + 1
            self.points = (self.points or 0) + 5
        else:
            self.streak_days = 1
            self.points = (self.points or 0) + 5
        self.last_login_date = today

    @property
    def has_active_subscription(self):
        if self.is_admin:
            return True
        return self.subscription_status == "active"

    def add_points(self, amount):
        self.points = (self.points or 0) + amount

    def ensure_referral_code(self):
        if not self.referral_code:
            self.referral_code = secrets.token_urlsafe(8)[:12]

    @property
    def tier(self):
        pts = self.points or 0
        if pts >= 5000:
            return "platinum"
        elif pts >= 2000:
            return "gold"
        elif pts >= 500:
            return "silver"
        return "bronze"

    @property
    def tier_display(self):
        return self.tier.capitalize()

    @property
    def level(self):
        pts = self.points or 0
        if pts >= 10000: return 10
        if pts >= 7000: return 9
        if pts >= 5000: return 8
        if pts >= 3500: return 7
        if pts >= 2500: return 6
        if pts >= 1500: return 5
        if pts >= 800: return 4
        if pts >= 400: return 3
        if pts >= 150: return 2
        return 1

    @property
    def level_title(self):
        titles = {
            1: "Newcomer", 2: "Member", 3: "Regular", 4: "Contributor",
            5: "Veteran", 6: "Elite", 7: "Champion", 8: "Legend",
            9: "Titan", 10: "Founder"
        }
        return titles.get(self.level, "Newcomer")

    @property
    def unread_message_count(self):
        return Message.query.join(Conversation).filter(
            ((Conversation.user1_id == self.id) | (Conversation.user2_id == self.id)),
            Message.sender_id != self.id,
            Message.is_read == False
        ).count()


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(300), default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    space_id = db.Column(db.Integer, db.ForeignKey("space.id"), default=None)

    comments = db.relationship("Comment", backref="post", lazy=True, cascade="all, delete-orphan",
                               order_by="Comment.created_at")
    likes = db.relationship("Like", backref="post", lazy=True, cascade="all, delete-orphan")
    poll = db.relationship("Poll", backref="post", uselist=False, cascade="all, delete-orphan")

    @property
    def like_count(self):
        return len(self.likes)

    def is_liked_by(self, user):
        return any(like.user_id == user.id for like in self.likes)

    @property
    def time_ago(self):
        now = datetime.utcnow()
        diff = now - self.created_at
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds // 60)
            return f"{mins}m ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours}h ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days}d ago"
        else:
            return self.created_at.strftime("%b %d, %Y")


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def time_ago(self):
        now = datetime.utcnow()
        diff = now - self.created_at
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds // 60)
            return f"{mins}m ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds // 86400)
            return f"{days}d ago"


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("post_id", "user_id", name="unique_like"),)


class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    follower = db.relationship("User", foreign_keys=[follower_id], backref="following_rel")
    followed = db.relationship("User", foreign_keys=[followed_id], backref="followers_rel")

    __table_args__ = (db.UniqueConstraint("follower_id", "followed_id", name="unique_follow"),)


class Space(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    cover_image = db.Column(db.String(300), default=None)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship("User", backref="created_spaces")
    posts = db.relationship("Post", backref="space", lazy=True)
    memberships = db.relationship("SpaceMembership", backref="space", lazy=True, cascade="all, delete-orphan")

    @property
    def member_count(self):
        return len(self.memberships)

    def is_member(self, user):
        return any(m.user_id == user.id for m in self.memberships)

    def get_role(self, user):
        m = SpaceMembership.query.filter_by(space_id=self.id, user_id=user.id).first()
        return m.role if m else None


class SpaceMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    space_id = db.Column(db.Integer, db.ForeignKey("space.id"), nullable=False)
    role = db.Column(db.String(20), default="member")  # member, moderator, admin
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="space_memberships")

    __table_args__ = (db.UniqueConstraint("user_id", "space_id", name="unique_space_member"),)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    type = db.Column(db.String(30), nullable=False)  # new_like, new_comment, new_follower, new_post_in_space
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(300), default=None)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def time_ago(self):
        now = datetime.utcnow()
        diff = now - self.created_at
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds // 60)
            return f"{mins}m ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds // 86400)
            return f"{days}d ago"


class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    question = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    options = db.relationship("PollOption", backref="poll", lazy=True, cascade="all, delete-orphan")

    @property
    def total_votes(self):
        return sum(len(opt.votes) for opt in self.options)

    def user_voted(self, user):
        for opt in self.options:
            if any(v.user_id == user.id for v in opt.votes):
                return True
        return False

    def user_vote_option_id(self, user):
        for opt in self.options:
            for v in opt.votes:
                if v.user_id == user.id:
                    return opt.id
        return None


class PollOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("poll.id"), nullable=False)
    text = db.Column(db.String(200), nullable=False)

    votes = db.relationship("PollVote", backref="option", lazy=True, cascade="all, delete-orphan")

    @property
    def vote_count(self):
        return len(self.votes)

    def percentage(self, total):
        if total == 0:
            return 0
        return round((self.vote_count / total) * 100)


class PollVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey("poll_option.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("option_id", "user_id", name="unique_poll_vote"),)


# ============ EVENTS ============

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(20), default="")
    location = db.Column(db.String(300), default="")
    host_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    cover_image = db.Column(db.String(300), default=None)
    max_attendees = db.Column(db.Integer, default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    host = db.relationship("User", backref="hosted_events")
    rsvps = db.relationship("EventRSVP", backref="event", lazy=True, cascade="all, delete-orphan")

    @property
    def going_count(self):
        return sum(1 for r in self.rsvps if r.status == "going")

    @property
    def interested_count(self):
        return sum(1 for r in self.rsvps if r.status == "interested")

    @property
    def is_past(self):
        return self.date < datetime.utcnow().date()

    def user_rsvp(self, user):
        """Return the RSVP status for a user, or None."""
        for r in self.rsvps:
            if r.user_id == user.id:
                return r.status
        return None


class EventRSVP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="going")  # going / interested / not_going
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="event_rsvps")

    __table_args__ = (db.UniqueConstraint("event_id", "user_id", name="unique_event_rsvp"),)


# ============ COURSES / LESSONS ============

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    cover_image = db.Column(db.String(300), default=None)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship("User", backref="created_courses")
    lessons = db.relationship("Lesson", backref="course", lazy=True, cascade="all, delete-orphan",
                              order_by="Lesson.order_index")

    def progress_for(self, user):
        """Return (completed, total) for a user."""
        total = len(self.lessons)
        if total == 0:
            return 0, 0
        completed = sum(
            1 for lesson in self.lessons
            if any(p.user_id == user.id and p.completed for p in lesson.progress)
        )
        return completed, total

    def progress_pct(self, user):
        completed, total = self.progress_for(user)
        return int((completed / total) * 100) if total > 0 else 0


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content_html = db.Column(db.Text, default="")
    video_url = db.Column(db.String(500), default=None)
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    progress = db.relationship("LessonProgress", backref="lesson", lazy=True, cascade="all, delete-orphan")

    def is_completed_by(self, user):
        return any(p.user_id == user.id and p.completed for p in self.progress)


class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, default=None)

    __table_args__ = (db.UniqueConstraint("lesson_id", "user_id", name="unique_lesson_progress"),)


# ============ WELCOME CHECKLIST ============

class ChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    link = db.Column(db.String(300), default="")
    order_index = db.Column(db.Integer, default=0)

    user_checks = db.relationship("UserChecklist", backref="item", lazy=True, cascade="all, delete-orphan")


class UserChecklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("checklist_item.id"), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, default=None)

    __table_args__ = (db.UniqueConstraint("user_id", "item_id", name="unique_user_checklist"),)


# ============ DIRECT MESSAGES ============

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    user1 = db.relationship("User", foreign_keys=[user1_id], backref="convos_as_user1")
    user2 = db.relationship("User", foreign_keys=[user2_id], backref="convos_as_user2")
    messages = db.relationship("Message", backref="conversation", lazy=True, cascade="all, delete-orphan",
                               order_by="Message.created_at")

    __table_args__ = (db.UniqueConstraint("user1_id", "user2_id", name="unique_conversation"),)

    def other_user(self, user):
        return self.user2 if self.user1_id == user.id else self.user1

    @property
    def last_message(self):
        return Message.query.filter_by(conversation_id=self.id).order_by(Message.created_at.desc()).first()

    def unread_count_for(self, user):
        return Message.query.filter_by(conversation_id=self.id, is_read=False).filter(
            Message.sender_id != user.id).count()


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_id])

    @property
    def time_ago(self):
        now = datetime.utcnow()
        diff = now - self.created_at
        seconds = diff.total_seconds()
        if seconds < 60: return "just now"
        elif seconds < 3600: return f"{int(seconds // 60)}m ago"
        elif seconds < 86400: return f"{int(seconds // 3600)}h ago"
        else: return f"{int(seconds // 86400)}d ago"


# ============ STORIES ============

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    image_path = db.Column(db.String(300), nullable=True)
    text_content = db.Column(db.Text, default="")
    bg_color = db.Column(db.String(20), default="#111111")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    author = db.relationship("User", backref="stories")
    views = db.relationship("StoryView", backref="story", lazy=True, cascade="all, delete-orphan")

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @property
    def view_count(self):
        return len(self.views)

    def viewed_by(self, user):
        return any(v.user_id == user.id for v in self.views)


class StoryView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("story.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("story_id", "user_id", name="unique_story_view"),)


# ============ WINS WALL ============

class Win(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    image_path = db.Column(db.String(300), default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", backref="wins")
    reactions = db.relationship("WinReaction", backref="win", lazy=True, cascade="all, delete-orphan")

    @property
    def time_ago(self):
        now = datetime.utcnow()
        diff = now - self.created_at
        seconds = diff.total_seconds()
        if seconds < 60: return "just now"
        elif seconds < 3600: return f"{int(seconds // 60)}m ago"
        elif seconds < 86400: return f"{int(seconds // 3600)}h ago"
        else: return f"{int(seconds // 86400)}d ago"

    def reaction_counts(self):
        counts = {}
        for r in self.reactions:
            counts[r.emoji] = counts.get(r.emoji, 0) + 1
        return counts

    def user_reacted(self, user, emoji):
        return any(r.user_id == user.id and r.emoji == emoji for r in self.reactions)


class WinReaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    win_id = db.Column(db.Integer, db.ForeignKey("win.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("win_id", "user_id", "emoji", name="unique_win_reaction"),)


# ============ DEAL BOARD ============

class Deal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(50), default="general")
    link = db.Column(db.String(500), default=None)
    image_path = db.Column(db.String(300), default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", backref="deals")
    interests = db.relationship("DealInterest", backref="deal", lazy=True, cascade="all, delete-orphan")

    CATEGORIES = ["general", "investment", "partnership", "service", "product", "hiring", "other"]

    @property
    def interest_count(self):
        return len(self.interests)

    def user_interested(self, user):
        return any(i.user_id == user.id for i in self.interests)

    @property
    def time_ago(self):
        now = datetime.utcnow()
        diff = now - self.created_at
        seconds = diff.total_seconds()
        if seconds < 60: return "just now"
        elif seconds < 3600: return f"{int(seconds // 60)}m ago"
        elif seconds < 86400: return f"{int(seconds // 3600)}h ago"
        else: return f"{int(seconds // 86400)}d ago"


class DealInterest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="deal_interests")
    __table_args__ = (db.UniqueConstraint("deal_id", "user_id", name="unique_deal_interest"),)


# ============ WEEKLY CHALLENGES ============

class WeeklyChallenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    points_reward = db.Column(db.Integer, default=50)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship("User", backref="created_challenges")
    submissions = db.relationship("ChallengeSubmission", backref="challenge", lazy=True, cascade="all, delete-orphan")

    @property
    def is_active(self):
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def is_past(self):
        return date.today() > self.end_date

    @property
    def submission_count(self):
        return len(self.submissions)


class ChallengeSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("weekly_challenge.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(300), default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", backref="challenge_submissions")
    votes = db.relationship("ChallengeVote", backref="submission", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("challenge_id", "user_id", name="unique_challenge_submission"),)

    @property
    def vote_count(self):
        return len(self.votes)

    def voted_by(self, user):
        return any(v.user_id == user.id for v in self.votes)


class ChallengeVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("challenge_submission.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("submission_id", "user_id", name="unique_challenge_vote"),)


# ============ RESOURCES VAULT ============

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    url = db.Column(db.String(500), default=None)
    category = db.Column(db.String(50), default="general")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", backref="resources")
    upvotes = db.relationship("ResourceUpvote", backref="resource", lazy=True, cascade="all, delete-orphan")

    CATEGORIES = ["book", "tool", "course", "podcast", "article", "video", "template", "general"]

    @property
    def upvote_count(self):
        return len(self.upvotes)

    def upvoted_by(self, user):
        return any(u.user_id == user.id for u in self.upvotes)


class ResourceUpvote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("resource_id", "user_id", name="unique_resource_upvote"),)


# ============ ACCOUNTABILITY ============

class MemberGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    target_date = db.Column(db.Date, default=None)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", backref="goals")
    checkins = db.relationship("GoalCheckIn", backref="goal", lazy=True, cascade="all, delete-orphan",
                               order_by="GoalCheckIn.created_at.desc()")


class AccountabilityPair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    user1 = db.relationship("User", foreign_keys=[user1_id], backref="accountability_as_user1")
    user2 = db.relationship("User", foreign_keys=[user2_id], backref="accountability_as_user2")

    __table_args__ = (db.UniqueConstraint("user1_id", "user2_id", name="unique_accountability_pair"),)


class GoalCheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey("member_goal.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User")


# ============ POST BOOKMARKS ============

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="bookmarks")
    post = db.relationship("Post", backref="bookmarks")

    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="unique_bookmark"),)


# ============ MEMBER BADGES ============

class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, default="")
    icon = db.Column(db.String(10), default="")
    points_required = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badge.id"), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="badges")
    badge = db.relationship("Badge", backref="earners")

    __table_args__ = (db.UniqueConstraint("user_id", "badge_id", name="unique_user_badge"),)


# ============ REELS ============

class Reel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), default="")
    video_url = db.Column(db.String(500), nullable=False)
    thumbnail_path = db.Column(db.String(300), default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", backref="reels")

    @property
    def embed_url(self):
        url = self.video_url
        if "youtube.com/watch" in url:
            vid = url.split("v=")[1].split("&")[0] if "v=" in url else ""
            return f"https://www.youtube.com/embed/{vid}"
        elif "youtu.be/" in url:
            vid = url.split("youtu.be/")[1].split("?")[0]
            return f"https://www.youtube.com/embed/{vid}"
        elif "vimeo.com/" in url:
            vid = url.split("vimeo.com/")[1].split("?")[0]
            return f"https://player.vimeo.com/video/{vid}"
        return url


# ============ SPACE CHAT ============

class SpaceChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    space_id = db.Column(db.Integer, db.ForeignKey("space.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User")
    space = db.relationship("Space", backref="chat_messages")

    @property
    def time_ago(self):
        now = datetime.utcnow()
        diff = now - self.created_at
        seconds = diff.total_seconds()
        if seconds < 60: return "just now"
        elif seconds < 3600: return f"{int(seconds // 60)}m ago"
        elif seconds < 86400: return f"{int(seconds // 3600)}h ago"
        else: return f"{int(seconds // 86400)}d ago"


# ============ AI WINGMAN ============

class AIChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # user or assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", backref="ai_chats")


# ============ CALL BOOKING ============

class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Mon, 6=Sun
    start_time = db.Column(db.String(5), nullable=False)  # "09:00"
    end_time = db.Column(db.String(5), nullable=False)  # "17:00"

    user = db.relationship("User", backref="availabilities")


class CallBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(5), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, confirmed, cancelled
    meeting_url = db.Column(db.String(500), default=None)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    booker = db.relationship("User", foreign_keys=[booker_id], backref="bookings_made")
    host = db.relationship("User", foreign_keys=[host_id], backref="bookings_received")


# ============ ACTIVITY FEED ============

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    detail = db.Column(db.Text, default="")
    link = db.Column(db.String(300), default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="activities")

    @property
    def time_ago(self):
        now = datetime.utcnow()
        diff = now - self.created_at
        seconds = diff.total_seconds()
        if seconds < 60: return "just now"
        elif seconds < 3600: return f"{int(seconds // 60)}m ago"
        elif seconds < 86400: return f"{int(seconds // 3600)}h ago"
        else: return f"{int(seconds // 86400)}d ago"
