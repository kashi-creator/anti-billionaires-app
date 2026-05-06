"""
Features Blueprint: All new ABMC features
DMs, Stories, Wins, Deals, Challenges, Resources, Accountability,
Bookmarks, Badges, Reels, Space Chat, AI Wingman, Map, Booking,
Boardroom, Activity Feed, Search, Referrals
"""
import os
import uuid
from datetime import datetime, timedelta, date
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, current_app, abort
)
from flask_login import login_required, current_user
from models import db
from models import (
    User, Post, Follow, Notification, Space, SpaceMembership,
    Conversation, Message,
    Story, StoryView,
    Win, WinReaction,
    Deal, DealInterest,
    WeeklyChallenge, ChallengeSubmission, ChallengeVote,
    Resource, ResourceUpvote,
    MemberGoal, AccountabilityPair, GoalCheckIn,
    Bookmark, Badge, UserBadge,
    Reel, SpaceChat, AIChat,
    Availability, CallBooking,
    Activity,
    Project, ProjectUpdate, ProjectInterest, ProjectPaymentMethod,
    PROJECT_STATUSES, PROJECT_TYPES, PROJECT_VISIBILITIES,
    PROJECT_PAYMENT_METHOD_TYPES,
)
import re

features = Blueprint('features', __name__)

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


def _create_notification(user_id, ntype, message, link=None):
    if user_id == current_user.id:
        return
    notif = Notification(user_id=user_id, type=ntype, message=message, link=link)
    db.session.add(notif)
    from lib import push as push_lib
    push_lib.send_push_to_user(user_id, "Sovereign", message, link or "/notifications")


def _log_activity(user_id, action, detail="", link=None):
    act = Activity(user_id=user_id, action=action, detail=detail, link=link)
    db.session.add(act)


# =====================================================================
#  DIRECT MESSAGES
# =====================================================================

@features.route('/messages')
@login_required
def inbox():
    convos = Conversation.query.filter(
        (Conversation.user1_id == current_user.id) |
        (Conversation.user2_id == current_user.id)
    ).order_by(Conversation.updated_at.desc()).all()
    return render_template('messages_inbox.html', conversations=convos)


@features.route('/messages/new/<int:user_id>')
@login_required
def new_conversation(user_id):
    if user_id == current_user.id:
        flash("You can't message yourself.", "error")
        return redirect(url_for('members'))
    user = User.query.get_or_404(user_id)
    # Check if conversation exists
    convo = _get_or_create_conversation(current_user.id, user_id)
    return redirect(url_for('features.chat', convo_id=convo.id))


def _get_or_create_conversation(uid1, uid2):
    u1, u2 = min(uid1, uid2), max(uid1, uid2)
    convo = Conversation.query.filter_by(user1_id=u1, user2_id=u2).first()
    if not convo:
        convo = Conversation(user1_id=u1, user2_id=u2)
        db.session.add(convo)
        db.session.commit()
    return convo


@features.route('/messages/<int:convo_id>')
@login_required
def chat(convo_id):
    convo = Conversation.query.get_or_404(convo_id)
    if current_user.id not in (convo.user1_id, convo.user2_id):
        abort(403)
    # Mark messages as read
    Message.query.filter_by(conversation_id=convo_id, is_read=False).filter(
        Message.sender_id != current_user.id
    ).update({"is_read": True})
    db.session.commit()
    other = convo.other_user(current_user)
    return render_template('messages_chat.html', conversation=convo, other_user=other)


@features.route('/messages/<int:convo_id>/send', methods=['POST'])
@login_required
def send_message(convo_id):
    convo = Conversation.query.get_or_404(convo_id)
    if current_user.id not in (convo.user1_id, convo.user2_id):
        return jsonify({"success": False}), 403
    content = request.json.get("content", "").strip() if request.is_json else request.form.get("content", "").strip()
    if not content:
        return jsonify({"success": False, "error": "Empty message"}), 400
    msg = Message(conversation_id=convo_id, sender_id=current_user.id, content=content)
    db.session.add(msg)
    convo.updated_at = datetime.utcnow()
    other_id = convo.user2_id if convo.user1_id == current_user.id else convo.user1_id
    _create_notification(other_id, "new_message", f"{current_user.name} sent you a message",
                         url_for('features.chat', convo_id=convo.id))
    db.session.commit()

    # Engagement email — debounced 1/hr per recipient
    try:
        from cron import notify_dm_throttled
        recipient = User.query.get(other_id)
        if recipient:
            notify_dm_throttled(recipient, current_user, content)
    except Exception as e:
        print(f"[DM email skip] {e}")
    return jsonify({
        "success": True,
        "message": {
            "id": msg.id,
            "content": msg.content,
            "sender_id": msg.sender_id,
            "time_ago": msg.time_ago,
            "created_at": msg.created_at.isoformat()
        }
    })


@features.route('/messages/<int:convo_id>/poll')
@login_required
def poll_messages(convo_id):
    convo = Conversation.query.get_or_404(convo_id)
    if current_user.id not in (convo.user1_id, convo.user2_id):
        return jsonify({"success": False}), 403
    after = request.args.get("after", 0, type=int)
    msgs = Message.query.filter(
        Message.conversation_id == convo_id,
        Message.id > after
    ).order_by(Message.created_at.asc()).all()
    # Mark as read
    for m in msgs:
        if m.sender_id != current_user.id and not m.is_read:
            m.is_read = True
    db.session.commit()
    return jsonify({
        "success": True,
        "messages": [{
            "id": m.id, "content": m.content, "sender_id": m.sender_id,
            "time_ago": m.time_ago, "created_at": m.created_at.isoformat()
        } for m in msgs]
    })


@features.route('/api/messages/unread-count')
@login_required
def api_unread_messages():
    count = current_user.unread_message_count
    return jsonify({"count": count})


# =====================================================================
#  STORIES
# =====================================================================

@features.route('/stories/create', methods=['POST'])
@login_required
def create_story():
    image_path = None
    if 'image' in request.files:
        f = request.files['image']
        if f.filename:
            image_path = _save_upload(f)
    text_content = request.form.get("text_content", "").strip()
    bg_color = request.form.get("bg_color", "#111111")

    if not image_path and not text_content:
        flash("Story needs an image or text.", "error")
        return redirect(url_for('feed'))

    story = Story(
        user_id=current_user.id,
        image_path=image_path,
        text_content=text_content,
        bg_color=bg_color,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db.session.add(story)
    current_user.add_points(5)
    db.session.commit()
    flash("Story posted!", "success")
    return redirect(url_for('feed'))


@features.route('/stories/<int:story_id>')
@login_required
def view_story(story_id):
    story = Story.query.get_or_404(story_id)
    if story.is_expired:
        flash("This story has expired.", "error")
        return redirect(url_for('feed'))
    # Record view
    if not story.viewed_by(current_user):
        view = StoryView(story_id=story.id, user_id=current_user.id)
        db.session.add(view)
        db.session.commit()
    return render_template('story_view.html', story=story)


@features.route('/api/stories')
@login_required
def api_stories():
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stories = Story.query.filter(Story.expires_at > datetime.utcnow(), Story.created_at > cutoff).order_by(
        Story.created_at.desc()).all()
    # Group by user
    users_with_stories = {}
    for s in stories:
        if s.user_id not in users_with_stories:
            users_with_stories[s.user_id] = {
                "user_id": s.user_id,
                "name": s.author.name,
                "photo": s.author.profile_photo,
                "stories": []
            }
        users_with_stories[s.user_id]["stories"].append({
            "id": s.id,
            "image_path": s.image_path,
            "text_content": s.text_content,
            "bg_color": s.bg_color,
            "viewed": s.viewed_by(current_user)
        })
    return jsonify({"success": True, "story_users": list(users_with_stories.values())})


# =====================================================================
#  WINS WALL
# =====================================================================

@features.route('/wins')
@login_required
def wins():
    all_wins = Win.query.order_by(Win.created_at.desc()).all()
    return render_template('wins.html', wins=all_wins)


@features.route('/wins/create', methods=['POST'])
@login_required
def create_win():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    if not title:
        flash("Win title is required.", "error")
        return redirect(url_for('features.wins'))
    image_path = None
    if 'image' in request.files:
        f = request.files['image']
        if f.filename:
            image_path = _save_upload(f)
    win = Win(user_id=current_user.id, title=title, description=description, image_path=image_path)
    db.session.add(win)
    current_user.add_points(15)
    _log_activity(current_user.id, "shared_win", f'Shared a win: "{title}"',
                  url_for('features.wins'))
    db.session.commit()
    flash("Win shared with the Society!", "success")
    return redirect(url_for('features.wins'))


@features.route('/wins/<int:win_id>/react', methods=['POST'])
@login_required
def react_win(win_id):
    win = Win.query.get_or_404(win_id)
    emoji = request.json.get("emoji", "")
    if not emoji:
        return jsonify({"success": False}), 400
    existing = WinReaction.query.filter_by(win_id=win_id, user_id=current_user.id, emoji=emoji).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"success": True, "action": "removed", "counts": win.reaction_counts()})
    reaction = WinReaction(win_id=win_id, user_id=current_user.id, emoji=emoji)
    db.session.add(reaction)
    _create_notification(win.user_id, "win_reaction", f"{current_user.name} reacted to your win",
                         url_for('features.wins'))
    db.session.commit()
    return jsonify({"success": True, "action": "added", "counts": win.reaction_counts()})


# =====================================================================
#  DEAL BOARD
# =====================================================================

@features.route('/deals')
@login_required
def deals():
    cat = request.args.get("category", "all")
    if cat and cat != "all":
        all_deals = Deal.query.filter_by(category=cat).order_by(Deal.created_at.desc()).all()
    else:
        all_deals = Deal.query.order_by(Deal.created_at.desc()).all()
    return render_template('deals.html', deals=all_deals, categories=Deal.CATEGORIES, selected_cat=cat)


@features.route('/deals/create', methods=['GET', 'POST'])
@login_required
def create_deal():
    if request.method == 'POST':
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "general")
        link = request.form.get("link", "").strip() or None
        if not title:
            flash("Deal title is required.", "error")
            return render_template('deal_create.html', categories=Deal.CATEGORIES)
        image_path = None
        if 'image' in request.files:
            f = request.files['image']
            if f.filename:
                image_path = _save_upload(f)
        deal = Deal(user_id=current_user.id, title=title, description=description,
                    category=category, link=link, image_path=image_path)
        db.session.add(deal)
        current_user.add_points(10)
        _log_activity(current_user.id, "posted_deal", f'Posted a deal: "{title}"',
                      url_for('features.deals'))
        db.session.commit()
        flash("Deal posted!", "success")
        return redirect(url_for('features.deals'))
    return render_template('deal_create.html', categories=Deal.CATEGORIES)


@features.route('/deals/<int:deal_id>')
@login_required
def deal_detail(deal_id):
    deal = Deal.query.get_or_404(deal_id)
    return render_template('deal_detail.html', deal=deal)


@features.route('/deals/<int:deal_id>/interest', methods=['POST'])
@login_required
def deal_interest(deal_id):
    deal = Deal.query.get_or_404(deal_id)
    existing = DealInterest.query.filter_by(deal_id=deal_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"success": True, "interested": False, "count": deal.interest_count})
    msg = request.json.get("message", "") if request.is_json else ""
    interest = DealInterest(deal_id=deal_id, user_id=current_user.id, message=msg)
    db.session.add(interest)
    _create_notification(deal.user_id, "deal_interest", f"{current_user.name} is interested in your deal",
                         url_for('features.deal_detail', deal_id=deal.id))
    db.session.commit()
    return jsonify({"success": True, "interested": True, "count": deal.interest_count})


# =====================================================================
#  PROJECTS — member-published builds (Phase 7)
# =====================================================================
# Sister to Deal. Members publish 0-N projects (businesses, products, missions);
# other members express interest, the creator posts progress updates over time.
# Visibility tiered: members_only (default) / brotherhood_only (Lifetime+) /
# private (creator-only, hidden from this phase's UI).
#
# Payment methods are a directory only — Sovereign Society does NOT process
# payments. The transaction happens off-platform, member-to-member. See the
# load-bearing disclaimer in `templates/project_detail.html`.
#
# Each route inlines the paywall+onboarding gate (mirrors `app.paywall_required`
# body) to dodge the existing `app.py → features_routes.py` import cycle.


def _project_paywall_or_redirect():
    """Return a redirect Response when the current user can't access projects;
    None when access is OK. Mirrors `app.paywall_required` body."""
    if not current_user.has_active_subscription:
        flash("Membership required to access this area.", "warning")
        return redirect(url_for('pricing'))
    if not current_user.onboarding_complete:
        return redirect(url_for('onboarding'))
    return None


def _visible_projects(query, user):
    """Filter a Project query to rows the given user can see, modulo the
    self-view exception (creator always sees own active projects regardless
    of visibility — applied separately by callers that want it).

    Visibility model:
    - lifetime_access (Lifetime+): members_only + brotherhood_only
    - has_active_subscription (no lifetime): members_only only
    - otherwise: nothing (paywall already blocks at the route level, so this
      branch is defensive)

    `private` is never returned by this helper — that tier is creator-only
    by design (Phase 7+ surface; not in this phase's UI).
    """
    query = query.filter(Project.is_active == True)
    if getattr(user, "lifetime_access", False):
        return query.filter(Project.visibility.in_(["members_only", "brotherhood_only"]))
    if getattr(user, "has_active_subscription", False):
        return query.filter(Project.visibility == "members_only")
    return query.filter(False)


@features.route('/projects')
@login_required
def projects():
    gate = _project_paywall_or_redirect()
    if gate:
        return gate
    status = (request.args.get("status") or "").strip()
    ptype = (request.args.get("type") or "").strip()
    q = _visible_projects(Project.query, current_user)
    if status in PROJECT_STATUSES:
        q = q.filter(Project.status == status)
    if ptype in PROJECT_TYPES:
        q = q.filter(Project.project_type == ptype)
    items = q.order_by(Project.updated_at.desc()).all()
    return render_template(
        'projects.html',
        projects=items,
        statuses=sorted(PROJECT_STATUSES),
        types=sorted(PROJECT_TYPES),
        selected_status=status,
        selected_type=ptype,
    )


@features.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create_project():
    gate = _project_paywall_or_redirect()
    if gate:
        return gate
    if request.method == 'POST':
        title = (request.form.get("title") or "").strip()
        summary = (request.form.get("summary") or "").strip()[:500]
        description = (request.form.get("description") or "").strip()
        status = (request.form.get("status") or "building").strip()
        ptype = (request.form.get("project_type") or "business").strip()
        looking_for = (request.form.get("looking_for") or "").strip()[:100]
        visibility = (request.form.get("visibility") or "members_only").strip()
        if not title:
            flash("Project title is required.", "error")
            return redirect(url_for('features.create_project'))
        if len(title) > 200:
            flash("Title is too long (max 200 chars).", "error")
            return redirect(url_for('features.create_project'))
        if status not in PROJECT_STATUSES:
            flash("Invalid status.", "error")
            return redirect(url_for('features.create_project'))
        if ptype not in PROJECT_TYPES:
            flash("Invalid project type.", "error")
            return redirect(url_for('features.create_project'))
        # Brotherhood_only restricted to Lifetime+ members.
        if visibility == "brotherhood_only" and not current_user.lifetime_access:
            visibility = "members_only"
        if visibility not in ("members_only", "brotherhood_only"):
            visibility = "members_only"
        cover_image = None
        if 'cover_image' in request.files:
            f = request.files['cover_image']
            if f and f.filename:
                cover_image = _save_upload(f)
        project = Project(
            user_id=current_user.id, title=title, summary=summary,
            description=description, status=status, project_type=ptype,
            looking_for=looking_for, visibility=visibility, cover_image=cover_image,
        )
        db.session.add(project)
        current_user.add_points(10)
        db.session.flush()
        _log_activity(
            current_user.id, "posted_project", f'Posted a project: "{title}"',
            url_for('features.project_detail', project_id=project.id),
        )
        db.session.commit()
        flash("Project posted.", "success")
        return redirect(url_for('features.project_detail', project_id=project.id))
    return render_template(
        'create_project.html',
        statuses=sorted(PROJECT_STATUSES),
        types=sorted(PROJECT_TYPES),
        can_brotherhood=current_user.lifetime_access,
    )


@features.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    gate = _project_paywall_or_redirect()
    if gate:
        return gate
    project = Project.query.get_or_404(project_id)
    is_creator = project.user_id == current_user.id
    # Self-view exception: creator can always see own project (any visibility,
    # archived included). Everyone else: must pass the visibility filter
    # AND the project must be active.
    if not is_creator:
        visible_ids = {p.id for p in _visible_projects(Project.query, current_user).all()}
        if project.id not in visible_ids:
            abort(404)
    return render_template(
        'project_detail.html',
        project=project,
        is_creator=is_creator,
        payment_method_types=sorted(PROJECT_PAYMENT_METHOD_TYPES.keys()),
    )


@features.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    gate = _project_paywall_or_redirect()
    if gate:
        return gate
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        title = (request.form.get("title") or "").strip()
        if not title or len(title) > 200:
            flash("Title required (max 200 chars).", "error")
            return redirect(url_for('features.edit_project', project_id=project.id))
        status = (request.form.get("status") or project.status).strip()
        ptype = (request.form.get("project_type") or project.project_type).strip()
        visibility = (request.form.get("visibility") or project.visibility).strip()
        if status not in PROJECT_STATUSES or ptype not in PROJECT_TYPES:
            flash("Invalid status or type.", "error")
            return redirect(url_for('features.edit_project', project_id=project.id))
        if visibility == "brotherhood_only" and not current_user.lifetime_access:
            visibility = "members_only"
        if visibility not in ("members_only", "brotherhood_only"):
            visibility = "members_only"
        project.title = title
        project.summary = (request.form.get("summary") or "").strip()[:500]
        project.description = (request.form.get("description") or "").strip()
        project.status = status
        project.project_type = ptype
        project.looking_for = (request.form.get("looking_for") or "").strip()[:100]
        project.visibility = visibility
        if 'cover_image' in request.files:
            f = request.files['cover_image']
            if f and f.filename:
                project.cover_image = _save_upload(f)
        db.session.commit()
        flash("Project updated.", "success")
        return redirect(url_for('features.project_detail', project_id=project.id))
    return render_template(
        'edit_project.html',
        project=project,
        statuses=sorted(PROJECT_STATUSES),
        types=sorted(PROJECT_TYPES),
        can_brotherhood=current_user.lifetime_access,
    )


@features.route('/projects/<int:project_id>/interest', methods=['POST'])
@login_required
def project_interest(project_id):
    gate = _project_paywall_or_redirect()
    if gate:
        return gate
    project = Project.query.get_or_404(project_id)
    # Visibility check: same as detail. Users can't toggle interest on a project
    # they couldn't see in the first place.
    if project.user_id != current_user.id:
        visible_ids = {p.id for p in _visible_projects(Project.query, current_user).all()}
        if project.id not in visible_ids:
            abort(404)
    existing = ProjectInterest.query.filter_by(
        project_id=project.id, user_id=current_user.id
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"success": True, "interested": False, "count": project.interest_count})
    msg = ""
    if request.is_json:
        msg = (request.json or {}).get("message", "")
    interest = ProjectInterest(project_id=project.id, user_id=current_user.id, message=msg)
    db.session.add(interest)
    if project.user_id != current_user.id:
        _create_notification(
            project.user_id, "project_interest",
            f"{current_user.name} is interested in your project: {project.title}",
            url_for('features.project_detail', project_id=project.id),
        )
    db.session.commit()
    return jsonify({"success": True, "interested": True, "count": project.interest_count})


@features.route('/projects/<int:project_id>/update', methods=['POST'])
@login_required
def project_update(project_id):
    gate = _project_paywall_or_redirect()
    if gate:
        return gate
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)
    content = (request.form.get("content") or "").strip()
    if not content:
        flash("Update content is required.", "error")
        return redirect(url_for('features.project_detail', project_id=project.id))
    image_path = None
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename:
            image_path = _save_upload(f)
    update = ProjectUpdate(
        project_id=project.id, user_id=current_user.id,
        content=content, image_path=image_path,
    )
    db.session.add(update)
    # Bump the project's updated_at so it floats to the top of the feed.
    project.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Update posted.", "success")
    return redirect(url_for('features.project_detail', project_id=project.id))


@features.route('/projects/<int:project_id>/archive', methods=['POST'])
@login_required
def project_archive(project_id):
    gate = _project_paywall_or_redirect()
    if gate:
        return gate
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)
    project.is_active = False
    db.session.commit()
    flash("Project archived. It is hidden from public feeds.", "success")
    return redirect(url_for('features.project_detail', project_id=project.id))


# ---- Payment methods (directory only — SS does NOT process payments) ----

PAYMENT_METHOD_SOFT_CAP = 10


@features.route('/projects/<int:project_id>/payment-method', methods=['POST'])
@login_required
def project_payment_method_add(project_id):
    gate = _project_paywall_or_redirect()
    if gate:
        return gate
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)
    if len(project.payment_methods) >= PAYMENT_METHOD_SOFT_CAP:
        flash(f"Soft cap of {PAYMENT_METHOD_SOFT_CAP} payment methods per project reached.", "error")
        return redirect(url_for('features.project_detail', project_id=project.id))
    method_type = (request.form.get("method_type") or "").strip()
    address = (request.form.get("address_or_handle") or "").strip()
    label = (request.form.get("label") or "").strip()[:100]
    pattern = PROJECT_PAYMENT_METHOD_TYPES.get(method_type)
    if not pattern:
        flash("Unknown payment method type.", "error")
        return redirect(url_for('features.project_detail', project_id=project.id))
    if not address or not re.fullmatch(pattern, address):
        flash(f"That doesn't look like a valid {method_type} address or handle.", "error")
        return redirect(url_for('features.project_detail', project_id=project.id))
    pm = ProjectPaymentMethod(
        project_id=project.id, method_type=method_type,
        address_or_handle=address, label=label,
        sort_order=len(project.payment_methods),
    )
    db.session.add(pm)
    db.session.commit()
    flash("Payment method added.", "success")
    return redirect(url_for('features.project_detail', project_id=project.id))


@features.route('/projects/<int:project_id>/payment-method/<int:pm_id>/delete', methods=['POST'])
@login_required
def project_payment_method_delete(project_id, pm_id):
    gate = _project_paywall_or_redirect()
    if gate:
        return gate
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)
    pm = ProjectPaymentMethod.query.get_or_404(pm_id)
    if pm.project_id != project.id:
        abort(404)
    db.session.delete(pm)
    db.session.commit()
    flash("Payment method removed.", "success")
    return redirect(url_for('features.project_detail', project_id=project.id))


# =====================================================================
#  WEEKLY CHALLENGES
# =====================================================================

@features.route('/challenges')
@login_required
def challenges():
    today = date.today()
    active = WeeklyChallenge.query.filter(
        WeeklyChallenge.start_date <= today,
        WeeklyChallenge.end_date >= today
    ).order_by(WeeklyChallenge.start_date.desc()).all()
    past = WeeklyChallenge.query.filter(WeeklyChallenge.end_date < today).order_by(
        WeeklyChallenge.end_date.desc()).limit(10).all()
    return render_template('challenges.html', active=active, past=past)


@features.route('/challenges/create', methods=['GET', 'POST'])
@login_required
def create_challenge():
    if not current_user.is_admin:
        flash("Only admins can create challenges.", "error")
        return redirect(url_for('features.challenges'))
    if request.method == 'POST':
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        start = request.form.get("start_date", "")
        end = request.form.get("end_date", "")
        pts = request.form.get("points_reward", "50")
        if not title or not start or not end:
            flash("Title, start date and end date required.", "error")
            return render_template('challenge_create.html')
        try:
            s = datetime.strptime(start, '%Y-%m-%d').date()
            e = datetime.strptime(end, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date.", "error")
            return render_template('challenge_create.html')
        ch = WeeklyChallenge(title=title, description=description, start_date=s, end_date=e,
                             points_reward=int(pts) if pts.isdigit() else 50,
                             created_by=current_user.id)
        db.session.add(ch)
        db.session.commit()
        flash("Challenge created!", "success")
        return redirect(url_for('features.challenges'))
    return render_template('challenge_create.html')


@features.route('/challenges/<int:ch_id>')
@login_required
def challenge_detail(ch_id):
    ch = WeeklyChallenge.query.get_or_404(ch_id)
    user_sub = ChallengeSubmission.query.filter_by(challenge_id=ch_id, user_id=current_user.id).first()
    subs = ChallengeSubmission.query.filter_by(challenge_id=ch_id).order_by(
        ChallengeSubmission.created_at.desc()).all()
    return render_template('challenge_detail.html', challenge=ch, user_submission=user_sub, submissions=subs)


@features.route('/challenges/<int:ch_id>/submit', methods=['POST'])
@login_required
def submit_challenge(ch_id):
    ch = WeeklyChallenge.query.get_or_404(ch_id)
    if not ch.is_active:
        flash("This challenge is no longer active.", "error")
        return redirect(url_for('features.challenge_detail', ch_id=ch_id))
    existing = ChallengeSubmission.query.filter_by(challenge_id=ch_id, user_id=current_user.id).first()
    if existing:
        flash("You already submitted.", "error")
        return redirect(url_for('features.challenge_detail', ch_id=ch_id))
    content = request.form.get("content", "").strip()
    if not content:
        flash("Submission content is required.", "error")
        return redirect(url_for('features.challenge_detail', ch_id=ch_id))
    image_path = None
    if 'image' in request.files:
        f = request.files['image']
        if f.filename:
            image_path = _save_upload(f)
    sub = ChallengeSubmission(challenge_id=ch_id, user_id=current_user.id, content=content, image_path=image_path)
    db.session.add(sub)
    current_user.add_points(ch.points_reward)
    db.session.commit()
    flash(f"Submission posted! +{ch.points_reward} points", "success")
    return redirect(url_for('features.challenge_detail', ch_id=ch_id))


@features.route('/challenges/submission/<int:sub_id>/vote', methods=['POST'])
@login_required
def vote_submission(sub_id):
    sub = ChallengeSubmission.query.get_or_404(sub_id)
    if sub.voted_by(current_user):
        return jsonify({"success": False, "error": "Already voted"}), 400
    vote = ChallengeVote(submission_id=sub_id, user_id=current_user.id)
    db.session.add(vote)
    sub.author.add_points(5)
    db.session.commit()
    return jsonify({"success": True, "votes": sub.vote_count})


# =====================================================================
#  RESOURCE VAULT
# =====================================================================

@features.route('/resources')
@login_required
def resources():
    cat = request.args.get("category", "all")
    if cat and cat != "all":
        all_res = Resource.query.filter_by(category=cat).order_by(Resource.created_at.desc()).all()
    else:
        all_res = Resource.query.order_by(Resource.created_at.desc()).all()
    return render_template('resources.html', resources=all_res, categories=Resource.CATEGORIES, selected_cat=cat)


@features.route('/resources/create', methods=['GET', 'POST'])
@login_required
def create_resource():
    if request.method == 'POST':
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        url_val = request.form.get("url", "").strip() or None
        category = request.form.get("category", "general")
        if not title:
            flash("Resource title is required.", "error")
            return render_template('resource_create.html', categories=Resource.CATEGORIES)
        res = Resource(user_id=current_user.id, title=title, description=description,
                       url=url_val, category=category)
        db.session.add(res)
        current_user.add_points(10)
        db.session.commit()
        flash("Resource shared!", "success")
        return redirect(url_for('features.resources'))
    return render_template('resource_create.html', categories=Resource.CATEGORIES)


@features.route('/resources/<int:res_id>/upvote', methods=['POST'])
@login_required
def upvote_resource(res_id):
    res = Resource.query.get_or_404(res_id)
    existing = ResourceUpvote.query.filter_by(resource_id=res_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"success": True, "upvoted": False, "count": res.upvote_count})
    upvote = ResourceUpvote(resource_id=res_id, user_id=current_user.id)
    db.session.add(upvote)
    res.author.add_points(2)
    db.session.commit()
    return jsonify({"success": True, "upvoted": True, "count": res.upvote_count})


# =====================================================================
#  REFERRAL SYSTEM
# =====================================================================

PAYMENTS_TO_QUALIFY = 6
QUALIFIED_NEEDED_FOR_LIFETIME = 3


@features.route('/referrals')
@login_required
def referrals():
    current_user.ensure_referral_code()
    db.session.commit()

    referred = User.query.filter_by(referred_by=current_user.id).order_by(User.created_at.desc()).all()

    # Classify each referral
    detailed = []
    qualified_count = 0
    paying_count = 0
    churned_count = 0
    for r in referred:
        payments = r.payments_made_count or 0
        is_qualified = payments >= PAYMENTS_TO_QUALIFY
        is_active = r.subscription_status == "active" or r.lifetime_access
        is_churned = (not is_active) and (not is_qualified)
        if is_qualified:
            qualified_count += 1
        elif is_active:
            paying_count += 1
        elif is_churned:
            churned_count += 1
        detailed.append({
            "user": r,
            "payments_made": payments,
            "payments_to_qualify": PAYMENTS_TO_QUALIFY,
            "is_qualified": is_qualified,
            "is_active": is_active,
            "is_churned": is_churned,
            "progress_pct": min(100, int((payments / PAYMENTS_TO_QUALIFY) * 100)),
        })

    # Use stored count if it disagrees with computed (stored is source of truth for billing).
    qualified_total = current_user.qualified_referrals_count or qualified_count
    remaining_to_lifetime = max(0, QUALIFIED_NEEDED_FOR_LIFETIME - qualified_total)
    progress_pct = min(100, int((qualified_total / QUALIFIED_NEEDED_FOR_LIFETIME) * 100))

    referral_url = f"{request.host_url.rstrip('/')}/r/{current_user.referral_code}"

    return render_template(
        'referrals.html',
        referral_code=current_user.referral_code,
        referral_url=referral_url,
        referred=detailed,
        qualified_count=qualified_total,
        paying_count=paying_count,
        churned_count=churned_count,
        threshold=QUALIFIED_NEEDED_FOR_LIFETIME,
        remaining_to_lifetime=remaining_to_lifetime,
        progress_pct=progress_pct,
        has_lifetime=current_user.lifetime_access,
        payments_to_qualify=PAYMENTS_TO_QUALIFY,
    )


@features.route('/r/<code>')
def referral_landing(code):
    user = User.query.filter_by(referral_code=code).first()
    if not user:
        return redirect(url_for('pricing'))
    # Store in session
    from flask import session
    session['referral_code'] = code
    return redirect(url_for('pricing'))


# =====================================================================
#  ACCOUNTABILITY PARTNERS
# =====================================================================

@features.route('/accountability')
@login_required
def accountability():
    # Find pairs
    pairs = AccountabilityPair.query.filter(
        ((AccountabilityPair.user1_id == current_user.id) | (AccountabilityPair.user2_id == current_user.id)),
        AccountabilityPair.is_active == True
    ).all()
    goals = MemberGoal.query.filter_by(user_id=current_user.id).order_by(MemberGoal.created_at.desc()).all()
    return render_template('accountability.html', pairs=pairs, goals=goals)


@features.route('/accountability/pair/<int:user_id>', methods=['POST'])
@login_required
def create_pair(user_id):
    if user_id == current_user.id:
        return jsonify({"success": False}), 400
    u1, u2 = min(current_user.id, user_id), max(current_user.id, user_id)
    existing = AccountabilityPair.query.filter_by(user1_id=u1, user2_id=u2).first()
    if existing:
        return jsonify({"success": False, "error": "Already paired"}), 400
    pair = AccountabilityPair(user1_id=u1, user2_id=u2)
    db.session.add(pair)
    _create_notification(user_id, "accountability", f"{current_user.name} wants to be your accountability partner",
                         url_for('features.accountability'))
    db.session.commit()
    return jsonify({"success": True})


@features.route('/accountability/goals/create', methods=['POST'])
@login_required
def create_goal():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    target = request.form.get("target_date", "")
    if not title:
        flash("Goal title is required.", "error")
        return redirect(url_for('features.accountability'))
    td = None
    if target:
        try:
            td = datetime.strptime(target, '%Y-%m-%d').date()
        except ValueError:
            pass
    goal = MemberGoal(user_id=current_user.id, title=title, description=description, target_date=td)
    db.session.add(goal)
    db.session.commit()
    flash("Goal created!", "success")
    return redirect(url_for('features.accountability'))


@features.route('/accountability/goals/<int:goal_id>/checkin', methods=['POST'])
@login_required
def goal_checkin(goal_id):
    goal = MemberGoal.query.get_or_404(goal_id)
    content = request.form.get("content", "").strip()
    if not content:
        flash("Check-in content is required.", "error")
        return redirect(url_for('features.accountability'))
    checkin = GoalCheckIn(goal_id=goal_id, user_id=current_user.id, content=content)
    db.session.add(checkin)
    current_user.add_points(5)
    db.session.commit()
    flash("Check-in logged!", "success")
    return redirect(url_for('features.accountability'))


@features.route('/accountability/goals/<int:goal_id>/complete', methods=['POST'])
@login_required
def complete_goal(goal_id):
    goal = MemberGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        abort(403)
    goal.is_completed = not goal.is_completed
    if goal.is_completed:
        current_user.add_points(25)
    db.session.commit()
    return jsonify({"success": True, "completed": goal.is_completed})


# =====================================================================
#  POST BOOKMARKS
# =====================================================================

@features.route('/bookmarks')
@login_required
def bookmarks():
    bmarks = Bookmark.query.filter_by(user_id=current_user.id).order_by(Bookmark.created_at.desc()).all()
    return render_template('bookmarks.html', bookmarks=bmarks)


@features.route('/bookmark/<int:post_id>', methods=['POST'])
@login_required
def toggle_bookmark(post_id):
    post = Post.query.get_or_404(post_id)
    existing = Bookmark.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"success": True, "bookmarked": False})
    bm = Bookmark(user_id=current_user.id, post_id=post_id)
    db.session.add(bm)
    db.session.commit()
    return jsonify({"success": True, "bookmarked": True})


# =====================================================================
#  BADGES / ACHIEVEMENTS
# =====================================================================

@features.route('/badges')
@login_required
def badges_page():
    all_badges = Badge.query.order_by(Badge.points_required.asc()).all()
    user_badge_ids = [ub.badge_id for ub in UserBadge.query.filter_by(user_id=current_user.id).all()]
    return render_template('badges.html', badges=all_badges, user_badge_ids=user_badge_ids)


def check_and_award_badges(user):
    """Check if user qualifies for any new badges."""
    all_badges = Badge.query.all()
    for badge in all_badges:
        if badge.points_required and (user.points or 0) >= badge.points_required:
            existing = UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first()
            if not existing:
                ub = UserBadge(user_id=user.id, badge_id=badge.id)
                db.session.add(ub)


def seed_badges():
    """Create default badges if none exist."""
    if Badge.query.count() > 0:
        return
    defaults = [
        ("First Steps", "Joined the Society", "1F4AA", 0),
        ("Contributor", "Earned 100 points", "2B50", 100),
        ("Rising Star", "Earned 500 points", "2B50", 500),
        ("Elite Member", "Earned 1000 points", "1F451", 1000),
        ("Gold Standard", "Earned 2000 points", "1F3C6", 2000),
        ("Platinum Force", "Earned 5000 points", "1F48E", 5000),
        ("Legend", "Earned 10000 points", "1F525", 10000),
    ]
    for name, desc, icon, pts in defaults:
        badge = Badge(name=name, description=desc, icon=icon, points_required=pts)
        db.session.add(badge)
    db.session.commit()


# =====================================================================
#  REELS
# =====================================================================

@features.route('/reels')
@login_required
def reels():
    all_reels = Reel.query.order_by(Reel.created_at.desc()).all()
    return render_template('reels.html', reels=all_reels)


@features.route('/reels/create', methods=['GET', 'POST'])
@login_required
def create_reel():
    if request.method == 'POST':
        title = request.form.get("title", "").strip()
        video_url = request.form.get("video_url", "").strip()
        if not video_url:
            flash("Video URL is required.", "error")
            return render_template('reel_create.html')
        reel = Reel(user_id=current_user.id, title=title, video_url=video_url)
        db.session.add(reel)
        current_user.add_points(15)
        db.session.commit()
        flash("Reel posted!", "success")
        return redirect(url_for('features.reels'))
    return render_template('reel_create.html')


# =====================================================================
#  SPACE CHAT
# =====================================================================

@features.route('/space/<int:space_id>/chat')
@login_required
def space_chat(space_id):
    space = Space.query.get_or_404(space_id)
    if not space.is_member(current_user):
        flash("Join the space to chat.", "error")
        return redirect(url_for('space_detail', space_id=space_id))
    msgs = SpaceChat.query.filter_by(space_id=space_id).order_by(SpaceChat.created_at.desc()).limit(100).all()
    msgs.reverse()
    return render_template('space_chat.html', space=space, messages=msgs)


@features.route('/space/<int:space_id>/chat/send', methods=['POST'])
@login_required
def send_space_chat(space_id):
    space = Space.query.get_or_404(space_id)
    if not space.is_member(current_user):
        return jsonify({"success": False}), 403
    content = request.json.get("content", "").strip() if request.is_json else ""
    if not content:
        return jsonify({"success": False}), 400
    msg = SpaceChat(space_id=space_id, user_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify({
        "success": True,
        "message": {
            "id": msg.id, "content": msg.content,
            "sender_id": msg.user_id, "sender_name": current_user.name,
            "sender_photo": current_user.profile_photo,
            "time_ago": msg.time_ago
        }
    })


@features.route('/space/<int:space_id>/chat/poll')
@login_required
def poll_space_chat(space_id):
    after = request.args.get("after", 0, type=int)
    msgs = SpaceChat.query.filter(
        SpaceChat.space_id == space_id,
        SpaceChat.id > after
    ).order_by(SpaceChat.created_at.asc()).all()
    return jsonify({
        "success": True,
        "messages": [{
            "id": m.id, "content": m.content,
            "sender_id": m.user_id, "sender_name": m.author.name,
            "sender_photo": m.author.profile_photo,
            "time_ago": m.time_ago
        } for m in msgs]
    })


# =====================================================================
#  AI WINGMAN
# =====================================================================

WINGMAN_SYSTEM_PROMPT = """You are the Wingman of Sovereign Society — a private network of operators, builders, and high-performers.

Your role:
- Sharp business advice (deal review, strategy, frameworks)
- Accountability nudges (call out drift, ask hard questions)
- Drafting (intros, pitches, replies, copy)
- Mindset and execution coaching

Your voice:
- Direct. No hedging, no fluff, no disclaimers.
- Confident but not cocky.
- Treat the member as a peer who's already accomplished.
- Push back when their thinking is weak.
- Brief by default; expand only when they ask.

Hard rules:
- Never recommend illegal activity, harm to self/others, or financial fraud.
- Don't claim to be a licensed professional (lawyer/CPA/doctor) — point them to one when needed.
- Don't moralize. They're adults.
"""


def _wingman_daily_cap():
    try:
        return int(os.environ.get("WINGMAN_DAILY_MESSAGE_CAP", "50"))
    except ValueError:
        return 50


def _wingman_today_count(user_id):
    return AIChat.query.filter_by(user_id=user_id, role="user").filter(
        AIChat.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()


@features.route('/wingman')
@login_required
def wingman():
    chats = AIChat.query.filter_by(user_id=current_user.id).order_by(AIChat.created_at.asc()).limit(50).all()
    daily_limit = _wingman_daily_cap()
    today_count = _wingman_today_count(current_user.id)
    return render_template('wingman.html', chats=chats, daily_limit=daily_limit,
                           today_count=today_count)


@features.route('/wingman/send', methods=['POST'])
@login_required
def wingman_send():
    content = (request.json.get("message", "") if request.is_json else request.form.get("message", "")).strip()
    if not content:
        return jsonify({"success": False, "error": "Empty message"}), 400
    if len(content) > 4000:
        return jsonify({"success": False, "error": "Message too long (max 4000 chars)"}), 400

    daily_limit = _wingman_daily_cap()
    today_count = _wingman_today_count(current_user.id)
    if today_count >= daily_limit:
        return jsonify({"success": False, "error": f"Daily Wingman cap reached ({daily_limit}). Resets at midnight UTC."}), 429

    user_msg = AIChat(user_id=current_user.id, role="user", content=content)
    db.session.add(user_msg)
    db.session.commit()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key or "placeholder" in api_key.lower() or "replace" in api_key.lower():
        reply = "AI Wingman isn't configured yet. The owner will plug in the Anthropic key shortly — keep grinding in the meantime."
    else:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            recent = AIChat.query.filter_by(user_id=current_user.id).order_by(
                AIChat.created_at.desc()).limit(20).all()
            recent.reverse()
            messages = [{"role": c.role, "content": c.content} for c in recent]

            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=WINGMAN_SYSTEM_PROMPT,
                messages=messages,
            )
            reply = response.content[0].text
        except Exception as e:
            print(f"[WINGMAN ERROR] {e}")
            reply = "Wingman hit an error. Try again in a moment."

    asst_msg = AIChat(user_id=current_user.id, role="assistant", content=reply)
    db.session.add(asst_msg)
    db.session.commit()

    return jsonify({"success": True, "reply": reply, "remaining": max(0, daily_limit - today_count - 1)})


# =====================================================================
#  MEMBER MAP
# =====================================================================

@features.route('/map')
@login_required
def member_map():
    members = User.query.filter(
        User.show_on_map == True,
        User.lat.isnot(None),
        User.lng.isnot(None)
    ).all()
    markers = [{
        "id": m.id, "name": m.name, "city": m.city or "",
        "country": m.country or "", "lat": m.lat, "lng": m.lng,
        "photo": m.profile_photo, "tier": m.tier
    } for m in members]
    return render_template('member_map.html', markers=markers)


@features.route('/profile/location', methods=['POST'])
@login_required
def update_location():
    from lib.geocoding import geocode_city
    current_user.city = request.form.get("city", "").strip() or None
    current_user.country = request.form.get("country", "").strip() or None
    lat = request.form.get("lat", "")
    lng = request.form.get("lng", "")
    coords_provided = False
    try:
        if lat and lng:
            current_user.lat = float(lat)
            current_user.lng = float(lng)
            coords_provided = True
    except ValueError:
        pass
    # If the user typed a city but didn't supply coords, resolve them so the
    # member shows up in Find Brothers search/proximity. Silent on failure —
    # the row still saves, just without coords.
    if not coords_provided and current_user.city:
        q = ", ".join(p for p in (current_user.city, current_user.country) if p)
        hit = geocode_city(q)
        if hit:
            current_user.lat = hit["lat"]
            current_user.lng = hit["lng"]
    current_user.show_on_map = request.form.get("show_on_map") == "on"
    db.session.commit()
    flash("Location updated.", "success")
    return redirect(url_for('edit_profile'))


@features.route('/profile/visibility', methods=['POST'])
@login_required
def update_location_visibility():
    """Phase 6: 3-tier privacy for the location feature."""
    val = (request.form.get("location_visibility") or "").strip()
    if val not in ("hidden", "city_only", "proximity_visible"):
        flash("Invalid visibility setting.", "error")
        return redirect(url_for('edit_profile'))
    current_user.location_visibility = val
    # Mirror legacy show_on_map so the existing /map page respects the choice.
    current_user.show_on_map = (val != "hidden")
    db.session.commit()
    flash("Location visibility updated.", "success")
    return redirect(url_for('edit_profile'))


# =====================================================================
#  FIND BROTHERS — search by city + proximity (Phase 6)
# =====================================================================

# Per-user rate limit on the geocoding endpoint. Nominatim's policy is ~1 req/sec
# globally; lru_cache absorbs repeats but a logged-in user could still hammer
# fresh queries. In-memory deque per user_id is sufficient for single-process
# Railway deploys.
from collections import deque
import time as _time
_FIND_SEARCH_HITS = {}  # user_id -> deque[timestamps]
_FIND_SEARCH_WINDOW_S = 60
_FIND_SEARCH_MAX_PER_WINDOW = 20

# Bounding-box queries (state/country/etc.) can return huge member lists; cap
# the response so the JSON stays bounded.
_FIND_BBOX_RESULT_CAP = 200
# Sanity cap on /find/nearby — without this, the "20 closest" can include
# someone on another continent in a sparse region.
_FIND_NEARBY_MAX_MILES = 100


def _find_search_rate_ok(user_id):
    now = _time.monotonic()
    hits = _FIND_SEARCH_HITS.setdefault(user_id, deque())
    while hits and now - hits[0] > _FIND_SEARCH_WINDOW_S:
        hits.popleft()
    if len(hits) >= _FIND_SEARCH_MAX_PER_WINDOW:
        return False
    hits.append(now)
    return True


@features.route('/find')
@login_required
def find_brothers():
    # Mirrors `app.paywall_required` body. Inlined to avoid a circular import
    # (features_routes is imported during app.py module load).
    if not current_user.has_active_subscription:
        flash("Membership required to access this area.", "warning")
        return redirect(url_for('pricing'))
    if not current_user.onboarding_complete:
        return redirect(url_for('onboarding'))
    return render_template('find.html')


@features.route('/find/search', methods=['POST'])
@login_required
def find_search():
    if not current_user.has_active_subscription:
        return jsonify({"error": "membership required"}), 403
    if not _find_search_rate_ok(current_user.id):
        return jsonify({"error": "slow down — too many searches, try again in a minute"}), 429
    from lib.geocoding import geocode_city, haversine_miles, in_bbox
    data = request.get_json(silent=True) or {}
    city = (data.get("city") or "").strip()
    try:
        radius = int(data.get("radius_miles") or 25)
    except (TypeError, ValueError):
        radius = 25
    radius = max(1, min(radius, 500))
    if not city:
        return jsonify({"error": "city required"}), 400
    hit = geocode_city(city)
    if not hit:
        return jsonify({"error": "could not locate that city"}), 400
    target_lat, target_lng = hit["lat"], hit["lng"]
    # State/country/region queries: filter by bounding box instead of radius.
    # Nominatim sets class=='boundary' for administrative regions.
    use_bbox = hit.get("osm_class") == "boundary" and hit.get("bbox")
    candidates = User.query.filter(
        User.location_visibility != "hidden",
        User.lat.isnot(None),
        User.lng.isnot(None),
    ).all()
    results = []
    for u in candidates:
        if u.id == current_user.id:
            continue
        d = haversine_miles(target_lat, target_lng, u.lat, u.lng)
        if use_bbox:
            if not in_bbox(u.lat, u.lng, hit["bbox"]):
                continue
        else:
            if d > radius:
                continue
        results.append({
            "id": u.id,
            "name": u.name,
            "city": u.city or "",
            "country": u.country or "",
            "miles": round(d, 1),
            "profile_photo": u.profile_photo,
        })
    results.sort(key=lambda x: x["miles"])
    if use_bbox:
        results = results[:_FIND_BBOX_RESULT_CAP]
    return jsonify({
        "results": results,
        "center": {"lat": target_lat, "lng": target_lng, "city": city},
        "mode": "region" if use_bbox else "radius",
    })


@features.route('/find/nearby', methods=['POST'])
@login_required
def find_nearby():
    if not current_user.has_active_subscription:
        return jsonify({"error": "membership required"}), 403
    from lib.geocoding import haversine_miles
    data = request.get_json(silent=True) or {}
    try:
        lat = float(data.get("lat"))
        lng = float(data.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "lat,lng required"}), 400
    candidates = User.query.filter(
        User.location_visibility == "proximity_visible",
        User.lat.isnot(None),
        User.lng.isnot(None),
    ).all()
    results = []
    for u in candidates:
        if u.id == current_user.id:
            continue
        d = haversine_miles(lat, lng, u.lat, u.lng)
        if d > _FIND_NEARBY_MAX_MILES:
            continue
        results.append({
            "id": u.id,
            "name": u.name,
            "city": u.city or "",
            "country": u.country or "",
            "miles": round(d, 1),
            "profile_photo": u.profile_photo,
        })
    results.sort(key=lambda x: x["miles"])
    return jsonify({"results": results[:20]})


# =====================================================================
#  1-ON-1 CALL BOOKING
# =====================================================================

@features.route('/book/<int:user_id>')
@login_required
def booking_page(user_id):
    host = User.query.get_or_404(user_id)
    if not host.bookings_enabled:
        flash("This member hasn't enabled bookings.", "error")
        return redirect(url_for('profile', user_id=user_id))
    avail = Availability.query.filter_by(user_id=user_id).order_by(Availability.day_of_week).all()
    return render_template('booking.html', host=host, availabilities=avail)


@features.route('/book/<int:user_id>/create', methods=['POST'])
@login_required
def create_booking(user_id):
    host = User.query.get_or_404(user_id)
    d = request.form.get("date", "")
    t = request.form.get("time", "")
    notes = request.form.get("notes", "").strip()
    if not d or not t:
        flash("Date and time required.", "error")
        return redirect(url_for('features.booking_page', user_id=user_id))
    try:
        bdate = datetime.strptime(d, '%Y-%m-%d').date()
    except ValueError:
        flash("Invalid date.", "error")
        return redirect(url_for('features.booking_page', user_id=user_id))
    booking = CallBooking(
        booker_id=current_user.id, host_id=user_id,
        date=bdate, time=t, notes=notes,
        meeting_url=host.default_meeting_url
    )
    db.session.add(booking)
    _create_notification(user_id, "new_booking", f"{current_user.name} booked a call with you",
                         url_for('features.my_bookings'))
    db.session.commit()
    flash("Booking requested!", "success")
    return redirect(url_for('features.my_bookings'))


@features.route('/bookings')
@login_required
def my_bookings():
    made = CallBooking.query.filter_by(booker_id=current_user.id).order_by(CallBooking.date.desc()).all()
    received = CallBooking.query.filter_by(host_id=current_user.id).order_by(CallBooking.date.desc()).all()
    return render_template('bookings.html', made=made, received=received)


@features.route('/bookings/<int:booking_id>/confirm', methods=['POST'])
@login_required
def confirm_booking(booking_id):
    booking = CallBooking.query.get_or_404(booking_id)
    if booking.host_id != current_user.id:
        abort(403)
    booking.status = "confirmed"
    _create_notification(booking.booker_id, "booking_confirmed",
                         f"{current_user.name} confirmed your call booking",
                         url_for('features.my_bookings'))
    db.session.commit()
    return jsonify({"success": True, "status": "confirmed"})


@features.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = CallBooking.query.get_or_404(booking_id)
    if current_user.id not in (booking.host_id, booking.booker_id):
        abort(403)
    booking.status = "cancelled"
    db.session.commit()
    return jsonify({"success": True, "status": "cancelled"})


# =====================================================================
#  VIRTUAL BOARDROOM (Platinum/Level 9+)
# =====================================================================

@features.route('/boardroom')
@login_required
def boardroom():
    if current_user.tier not in ("platinum",) and current_user.level < 9 and not current_user.is_admin:
        flash("The Boardroom is exclusive to Platinum members and Level 9+.", "error")
        return redirect(url_for('feed'))
    posts = Post.query.filter_by(space_id=None).order_by(Post.created_at.desc()).limit(20).all()
    members = User.query.filter(
        (User.points >= 5000) | (User.is_admin == True)
    ).order_by(User.points.desc()).all()
    return render_template('boardroom.html', posts=posts, members=members)


# =====================================================================
#  MEMBER SPOTLIGHTS
# =====================================================================

@features.route('/spotlights')
@login_required
def spotlights():
    # Get top 5 users by points earned this week (simple version)
    top = User.query.order_by(User.points.desc()).limit(5).all()
    return render_template('spotlights.html', spotlight_members=top)


# =====================================================================
#  ACTIVITY FEED
# =====================================================================

@features.route('/activity')
@login_required
def activity_feed():
    activities = Activity.query.order_by(Activity.created_at.desc()).limit(50).all()
    return render_template('activity_feed.html', activities=activities)


# =====================================================================
#  FULL-TEXT SEARCH
# =====================================================================

@features.route('/search')
@login_required
def search():
    q = request.args.get("q", "").strip()
    results = {"users": [], "posts": [], "spaces": [], "deals": [], "resources": []}
    if q:
        results["users"] = User.query.filter(User.name.ilike(f"%{q}%")).limit(10).all()
        results["posts"] = Post.query.filter(Post.content.ilike(f"%{q}%")).order_by(Post.created_at.desc()).limit(10).all()
        results["spaces"] = Space.query.filter(Space.name.ilike(f"%{q}%")).limit(10).all()
        results["deals"] = Deal.query.filter(Deal.title.ilike(f"%{q}%")).limit(10).all()
        results["resources"] = Resource.query.filter(Resource.title.ilike(f"%{q}%")).limit(10).all()
    return render_template('search.html', query=q, results=results)
