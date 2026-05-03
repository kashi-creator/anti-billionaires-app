"""
Phase 3 Blueprint: Events, Lessons/Courses, Welcome Checklist
Register with: app.register_blueprint(phase3)
"""
import os
import uuid
from datetime import datetime, date
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db
from models import (
    Event, EventRSVP,
    Course, Lesson, LessonProgress,
    ChecklistItem, UserChecklist,
)

phase3 = Blueprint('phase3', __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _paywall_required(f):
    """Local mirror of app.paywall_required — defined here to avoid the
    circular import (app.py already imports this module). Stacks AFTER
    @login_required: assumes current_user is authenticated."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.has_active_subscription:
            flash("Membership required to access this area.", "warning")
            return redirect(url_for('pricing'))
        return f(*args, **kwargs)
    return wrapper


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_upload(file):
    if file and _allowed(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        upload_dir = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, filename))
        return f"uploads/{filename}"
    return None


# =====================================================================
#  EVENTS
# =====================================================================

@phase3.route('/events')
@login_required
@_paywall_required
def events():
    # Cheap idempotent extension of the rolling 8-week window on every GET.
    # _generate_upcoming_occurrences skips dates that already have a child row,
    # so the only cost when the window is full is one SELECT per template.
    from app import _generate_upcoming_occurrences
    for template in Event.query.filter_by(is_recurrence_template=True).all():
        _generate_upcoming_occurrences(template, weeks_ahead=8)
    db.session.commit()

    today = date.today()
    upcoming_chapter = Event.query.filter(
        Event.is_recurrence_template == False,
        Event.event_type == "chapter_recurring",
        Event.date >= today,
    ).order_by(Event.chapter.asc(), Event.date.asc()).all()
    upcoming_weekly = Event.query.filter(
        Event.is_recurrence_template == False,
        Event.event_type == "weekly_recurring",
        Event.date >= today,
    ).order_by(Event.date.asc()).all()
    upcoming_meetups = Event.query.filter(
        Event.is_recurrence_template == False,
        Event.event_type == "member_meetup",
        Event.date >= today,
    ).order_by(Event.date.asc()).all()

    chapters_grouped = {}
    for ev in upcoming_chapter:
        chapters_grouped.setdefault(ev.chapter or "Unassigned", []).append(ev)

    return render_template(
        'events.html',
        chapters_grouped=chapters_grouped,
        upcoming_weekly=upcoming_weekly,
        upcoming_meetups=upcoming_meetups,
    )


@phase3.route('/events/<int:event_id>')
@login_required
@_paywall_required
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    user_status = event.user_rsvp(current_user)
    going_users = [r.user for r in event.rsvps if r.status == "going"]
    interested_users = [r.user for r in event.rsvps if r.status == "interested"]
    return render_template('event_detail.html', event=event, user_status=user_status,
                           going_users=going_users, interested_users=interested_users)


@phase3.route('/events/create', methods=['GET', 'POST'])
@login_required
@_paywall_required
def create_event():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        date_str = request.form.get('date', '')
        time_str = request.form.get('time', '').strip()
        location = request.form.get('location', '').strip()
        max_att = request.form.get('max_attendees', '').strip()
        chapter = request.form.get('chapter', '').strip() or None

        if not title or not date_str:
            flash("Title and date are required.", "error")
            return render_template('event_create.html')

        try:
            event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format.", "error")
            return render_template('event_create.html')

        cover_image = None
        if 'cover_image' in request.files:
            f = request.files['cover_image']
            if f.filename:
                cover_image = _save_upload(f)

        # Server-side gate: only admins can pick event_type / recurrence_rule.
        # Members are forced into member_meetup with no recurrence regardless of
        # what the form body claims.
        if current_user.is_admin:
            event_type = request.form.get('event_type', 'member_meetup').strip()
            recurrence_rule = request.form.get('recurrence_rule', 'none').strip()
            is_template = recurrence_rule != 'none'
        else:
            event_type = 'member_meetup'
            recurrence_rule = 'none'
            is_template = False

        try:
            event = Event(
                title=title,
                description=description,
                date=event_date,
                time=time_str,
                location=location,
                host_id=current_user.id,
                cover_image=cover_image,
                max_attendees=int(max_att) if max_att.isdigit() else None,
                event_type=event_type,
                chapter=chapter,
                recurrence_rule=recurrence_rule,
                is_recurrence_template=is_template,
            )
        except ValueError as e:
            flash(f"Invalid event: {e}", "error")
            return render_template('event_create.html')

        db.session.add(event)
        db.session.commit()

        # If admin created a recurrence template, materialize the next 8 weeks now.
        if is_template:
            from app import _generate_upcoming_occurrences
            _generate_upcoming_occurrences(event, weeks_ahead=8)
            db.session.commit()

        flash("Event created.", "success")
        return redirect(url_for('phase3.event_detail', event_id=event.id))

    return render_template('event_create.html')


@phase3.route('/events/<int:event_id>/rsvp', methods=['POST'])
@login_required
@_paywall_required
def event_rsvp(event_id):
    event = Event.query.get_or_404(event_id)
    status = request.form.get('status', 'going')

    if status not in ('going', 'interested', 'not_going'):
        flash("Invalid RSVP status.", "error")
        return redirect(url_for('phase3.event_detail', event_id=event_id))

    existing = EventRSVP.query.filter_by(event_id=event_id, user_id=current_user.id).first()

    if status == 'not_going':
        if existing:
            db.session.delete(existing)
            db.session.commit()
        flash("RSVP removed.", "success")
    else:
        if existing:
            existing.status = status
        else:
            rsvp = EventRSVP(event_id=event_id, user_id=current_user.id, status=status)
            db.session.add(rsvp)
        db.session.commit()
        label = "Going" if status == "going" else "Interested"
        flash(f"You're marked as {label}.", "success")

        _check_item_by_slug(current_user.id, "rsvp-event")

    return redirect(url_for('phase3.event_detail', event_id=event_id))


# =====================================================================
#  COURSES / LESSONS
# =====================================================================

@phase3.route('/lessons')
@login_required
def lessons():
    courses = Course.query.order_by(Course.order_index.asc()).all()
    return render_template('lessons.html', courses=courses)


@phase3.route('/lessons/<int:course_id>/<int:lesson_id>')
@login_required
def lesson_detail(course_id, lesson_id):
    course = Course.query.get_or_404(course_id)
    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course_id).first_or_404()
    completed = lesson.is_completed_by(current_user)
    # Find prev/next lesson
    idx = next((i for i, l in enumerate(course.lessons) if l.id == lesson.id), 0)
    prev_lesson = course.lessons[idx - 1] if idx > 0 else None
    next_lesson = course.lessons[idx + 1] if idx < len(course.lessons) - 1 else None
    return render_template('lesson_detail.html', course=course, lesson=lesson,
                           completed=completed, prev_lesson=prev_lesson, next_lesson=next_lesson)


@phase3.route('/lessons/<int:course_id>/<int:lesson_id>/complete', methods=['POST'])
@login_required
def complete_lesson(course_id, lesson_id):
    lesson = Lesson.query.filter_by(id=lesson_id, course_id=course_id).first_or_404()
    progress = LessonProgress.query.filter_by(lesson_id=lesson_id, user_id=current_user.id).first()

    if progress:
        progress.completed = not progress.completed
        progress.completed_at = datetime.utcnow() if progress.completed else None
    else:
        progress = LessonProgress(lesson_id=lesson_id, user_id=current_user.id,
                                  completed=True, completed_at=datetime.utcnow())
        db.session.add(progress)

    db.session.commit()

    _check_item_by_slug(current_user.id, "complete-lesson")

    return redirect(url_for('phase3.lesson_detail', course_id=course_id, lesson_id=lesson_id))


# =====================================================================
#  WELCOME CHECKLIST
# =====================================================================

@phase3.route('/welcome')
@login_required
def welcome():
    items = ChecklistItem.query.order_by(ChecklistItem.order_index.asc()).all()
    # Ensure UserChecklist rows exist for this user
    for item in items:
        uc = UserChecklist.query.filter_by(user_id=current_user.id, item_id=item.id).first()
        if not uc:
            uc = UserChecklist(user_id=current_user.id, item_id=item.id)
            db.session.add(uc)
    db.session.commit()

    checklist = []
    for item in items:
        uc = UserChecklist.query.filter_by(user_id=current_user.id, item_id=item.id).first()
        checklist.append({'item': item, 'completed': uc.completed if uc else False})

    total = len(checklist)
    done = sum(1 for c in checklist if c['completed'])
    pct = int((done / total) * 100) if total > 0 else 0

    return render_template('welcome.html', checklist=checklist, total=total, done=done, pct=pct)


@phase3.route('/welcome/check/<int:item_id>', methods=['POST'])
@login_required
def check_item(item_id):
    uc = UserChecklist.query.filter_by(user_id=current_user.id, item_id=item_id).first()
    if not uc:
        uc = UserChecklist(user_id=current_user.id, item_id=item_id)
        db.session.add(uc)

    uc.completed = not uc.completed
    uc.completed_at = datetime.utcnow() if uc.completed else None
    db.session.commit()
    return redirect(url_for('phase3.welcome'))


def _check_item_by_slug(user_id, slug):
    """Mark a checklist item complete by canonical slug. Idempotent."""
    item = ChecklistItem.query.filter_by(slug=slug).first()
    if not item:
        return
    uc = UserChecklist.query.filter_by(user_id=user_id, item_id=item.id).first()
    if not uc:
        uc = UserChecklist(user_id=user_id, item_id=item.id, completed=True, completed_at=datetime.utcnow())
        db.session.add(uc)
    elif not uc.completed:
        uc.completed = True
        uc.completed_at = datetime.utcnow()
    else:
        return  # already complete, no commit needed
    db.session.commit()


def _auto_check_item(user_id, title_substring):
    """Legacy shim — title-substring matcher kept for any pre-existing caller.
    Prefer `_check_item_by_slug` for new code."""
    item = ChecklistItem.query.filter(ChecklistItem.title.ilike(f'%{title_substring}%')).first()
    if not item:
        return
    uc = UserChecklist.query.filter_by(user_id=user_id, item_id=item.id).first()
    if not uc:
        uc = UserChecklist(user_id=user_id, item_id=item.id, completed=True, completed_at=datetime.utcnow())
        db.session.add(uc)
    elif not uc.completed:
        uc.completed = True
        uc.completed_at = datetime.utcnow()
    else:
        return
    db.session.commit()


# =====================================================================
#  SEED DEFAULT CHECKLIST (call once)
# =====================================================================

def seed_checklist():
    """Create/update the 7 canonical checklist items.

    Self-heals legacy data: backfills slug by exact title match or known
    legacy aliases (so a member who completed "Introduce Yourself" keeps
    credit under "Make your first post"). The legacy "RSVP to Fire to Fire"
    row is wiped wholesale since the underlying event was rewritten in Phase 3
    — completions against a now-deleted event are not transferable. Any other
    slugless row left over is also swept so the table converges to the 7
    canonical items."""
    desired = [
        # (slug, title, description, link, legacy aliases to absorb)
        ("complete-profile",  "Complete your profile",  "Add a photo and bio so the brotherhood knows who you are.", "/profile/edit",        []),
        ("read-manifesto",    "Read the Manifesto",     "The founding manifesto. Read it before anything else.",     "/manifesto",            []),
        ("first-post",        "Make your first post",   "Drop into the feed. Who you are, what you're building, what you need.", "/feed?focus=composer", ["Introduce Yourself"]),
        ("join-space",        "Join a Space",           "Pick a Space that fits you and join the conversation.",     "/spaces",               ["Join 2 Spaces"]),
        ("follow-brothers",   "Follow 3 brothers",      "Connect with other members. Build your circle.",            "/members",              ["Follow 5 Brothers"]),
        ("rsvp-event",        "RSVP to an event",       "Show up. Whether it's a chapter biweekly or a member meetup, get in the room.", "/events", []),
        ("complete-lesson",   "Complete a lesson",      "Open The Vault and finish your first lesson.",              "/lessons",              []),
    ]
    changed = False

    # Wipe the legacy Fire to Fire row up front so the rsvp-event slug can't
    # absorb a completion against an event that no longer exists.
    legacy_f2f = ChecklistItem.query.filter(ChecklistItem.title.ilike("%fire to fire%")).first()
    if legacy_f2f:
        UserChecklist.query.filter_by(item_id=legacy_f2f.id).delete()
        db.session.delete(legacy_f2f)
        db.session.flush()
        changed = True

    for i, (slug, title, desc, link, aliases) in enumerate(desired):
        existing = ChecklistItem.query.filter_by(slug=slug).first() \
                   or ChecklistItem.query.filter_by(title=title).first()
        if not existing:
            for alias in aliases:
                existing = ChecklistItem.query.filter_by(title=alias).first()
                if existing:
                    break
        if existing:
            existing.slug = slug
            existing.title = title
            existing.description = desc
            existing.link = link
            existing.order_index = i
        else:
            db.session.add(ChecklistItem(slug=slug, title=title, description=desc, link=link, order_index=i))
        changed = True

    canonical_slugs = {row[0] for row in desired}
    for orphan in ChecklistItem.query.all():
        if orphan.slug not in canonical_slugs:
            UserChecklist.query.filter_by(item_id=orphan.id).delete()
            db.session.delete(orphan)
            changed = True

    if changed:
        db.session.commit()
