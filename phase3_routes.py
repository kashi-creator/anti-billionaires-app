"""
Phase 3 Blueprint: Events, Lessons/Courses, Welcome Checklist
Register with: app.register_blueprint(phase3)
"""
import os
import uuid
from datetime import datetime
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
def events():
    today = datetime.utcnow().date()
    upcoming = Event.query.filter(Event.date >= today).order_by(Event.date.asc()).all()
    past = Event.query.filter(Event.date < today).order_by(Event.date.desc()).all()
    return render_template('events.html', upcoming=upcoming, past=past)


@phase3.route('/events/<int:event_id>')
@login_required
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    user_status = event.user_rsvp(current_user)
    going_users = [r.user for r in event.rsvps if r.status == "going"]
    interested_users = [r.user for r in event.rsvps if r.status == "interested"]
    return render_template('event_detail.html', event=event, user_status=user_status,
                           going_users=going_users, interested_users=interested_users)


@phase3.route('/events/create', methods=['GET', 'POST'])
@login_required
def create_event():
    if not current_user.is_admin:
        flash("Only admins can create events.", "error")
        return redirect(url_for('phase3.events'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        date_str = request.form.get('date', '')
        time_str = request.form.get('time', '').strip()
        location = request.form.get('location', '').strip()
        max_att = request.form.get('max_attendees', '').strip()

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

        event = Event(
            title=title,
            description=description,
            date=event_date,
            time=time_str,
            location=location,
            host_id=current_user.id,
            cover_image=cover_image,
            max_attendees=int(max_att) if max_att.isdigit() else None,
        )
        db.session.add(event)
        db.session.commit()
        flash("Event created.", "success")
        return redirect(url_for('phase3.event_detail', event_id=event.id))

    return render_template('event_create.html')


@phase3.route('/events/<int:event_id>/rsvp', methods=['POST'])
@login_required
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

        # Auto-check "RSVP to an event" checklist item
        _auto_check_item(current_user.id, "RSVP")

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

    # Auto-check "Complete a lesson" checklist item
    _auto_check_item(current_user.id, "Complete a lesson")

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


def _auto_check_item(user_id, title_substring):
    """Automatically mark a checklist item as completed by partial title match."""
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
    db.session.commit()


# =====================================================================
#  SEED DEFAULT CHECKLIST (call once)
# =====================================================================

def seed_checklist():
    """Create default checklist items if none exist."""
    if ChecklistItem.query.count() > 0:
        return
    defaults = [
        ("Complete your profile", "Add a bio and profile photo to let the brotherhood know who you are.", "/profile/edit"),
        ("Make your first post", "Share something with the club in the feed.", "/feed"),
        ("Join a Space", "Find a Space that interests you and join the conversation.", "/spaces"),
        ("Follow 3 members", "Connect with 3 other members of the brotherhood.", "/members"),
        ("RSVP to an event", "Check out upcoming events and mark yourself as Going.", "/events"),
        ("Complete a lesson", "Start learning by completing your first lesson.", "/lessons"),
    ]
    for i, (title, desc, link) in enumerate(defaults):
        item = ChecklistItem(title=title, description=desc, link=link, order_index=i)
        db.session.add(item)
    db.session.commit()
