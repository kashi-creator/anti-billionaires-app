# Phase 3 — Events stack rework: chapters, recurring, member meetups

> Paste this entire prompt into a fresh Claude Code session opened in `/Users/kenneth/anti-billionaires-app`. **Goal:** evolve the Events feature from "3 hardcoded one-off events" into "chapter recurring + global recurring + member-uploaded local meetups."
>
> Runs in parallel with Phase 2 (Space cover image fix). Disjoint files: Phase 2 only touches `_seed_content`'s spaces section + spaces template; Phase 3 touches event model, event templates, event routes, and the events portion of `_seed_content`.

---

## Step 0 — Pull before reading

```bash
git fetch origin && git status
```

If `main` is behind origin: `git reset --hard origin/main` (after confirming no uncommitted local work).

---

## Step 1 — Read first (mandatory)

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — full file. Pay attention to §1 (live URL, ownership), §3 (App Scope: Events area exists), §9 Decisions Log "Post-Phase-1 vision" entry which previewed this work.
2. `models.py` — `Event` and `EventRSVP` models. Existing fields: `id, title, description, date (Date), time (string), location, host_id, cover_image, max_attendees, created_at`. **Schema is changing — see step 3.1.**
3. `phase3_routes.py` — 4 routes: `/events`, `/events/<id>`, `/events/create` (currently admin-only), `/events/<id>/rsvp`.
4. `templates/events.html`, `templates/event_detail.html`, `templates/create_event.html` — current templates.
5. `app.py` `_seed_content()` — currently creates 3 hardcoded events. **You will replace this section** with the new event seeding.
6. `migrations/versions/` — note migration count (last revision id and chain). Your new migration extends the chain.

---

## Step 2 — The decisions this phase encodes (manager has locked these)

### 2.1 Three event types

| `event_type` value | Meaning | Created by | Recurrence |
|---|---|---|---|
| `chapter_recurring` | Official chapter biweekly/monthly meetup | Admin only | Yes (e.g. first+last Thursday monthly) |
| `weekly_recurring` | Official weekly recurring (e.g. Thursday lunch) | Admin only | Yes (every week) |
| `member_meetup` | A member organizing a local meetup, one-off or self-managed | Any active member | None (single date) |

(Reserved for future: `official_one_off` for non-recurring official events like the annual Brotherhood Summit. Not used in this phase, but the enum should accept it for forward-compat.)

### 2.2 Chapters

Add a `chapter` string field. Free-form for now (no FK to a Chapter model — premature). Convention: city + state, title-cased. Examples: `St. Petersburg, FL`, `Austin, TX`, `Global` (for events that aren't tied to a city — the Thursday lunch is `Global` since it alternates locations weekly), or NULL (member meetups can leave it null or set their own).

### 2.3 Recurrence model

Add a `recurrence_rule` string field. Locked vocabulary (executor MUST validate against this list — raise on anything else):

| Value | Meaning |
|---|---|
| `none` | Single occurrence on `date`. Default. |
| `every_thursday` | Recurs every Thursday. |
| `first_and_last_thursday_monthly` | The 1st Thursday and the last Thursday of each month. |

Two recurrence rules cover everything Kashi specified. Don't try to build a general RFC 5545 RRULE engine — this isn't Google Calendar, and adding scope here drags the phase out by days.

### 2.4 Recurrence display approach

**Strategy: each calendar occurrence is its own Event row, generated from a "template" row.** Rationale: the existing `EventRSVP` model joins by `event_id`; if you make occurrences ephemeral, RSVPs can't be attached. Per-occurrence rows preserve all existing logic and let people RSVP to "the May 7 Thursday lunch" specifically without breaking when next week's lunch is added.

Implementation:
- Add `recurrence_parent_id` (nullable FK to `event.id`) on `Event`. Each recurrence parent points at itself, occurrences point at the parent.
- A small helper function `_generate_upcoming_occurrences(parent_event, weeks_ahead=8)` creates the next 8 weeks of occurrences for any recurring template, with idempotency (skip if an occurrence with the same `recurrence_parent_id + date` already exists).
- Call the helper from `_seed_content()` AFTER seeding the templates, to pre-create the next 8 weeks. Also call it on every `/events` GET (cheap idempotent check) so the calendar always extends 8 weeks into the future.
- Mark the template row with a flag (`is_recurrence_template = True` boolean). Templates don't show up in `/events` list — only their generated children do.

### 2.5 Member meetup permissions

Open `/events/create` to any user where `current_user.has_active_subscription or current_user.lifetime_access`. Members creating events can ONLY set `event_type=member_meetup`. The `chapter`, `event_type=chapter_recurring|weekly_recurring`, and recurrence fields are admin-only — gated server-side, hidden client-side on the form.

### 2.6 Replace existing 3 seeded events

The three currently-seeded events (`Fire to Fire - St. Pete`, `Sovereign Wealth Workshop`, `Brotherhood Summit`) are stale. Phase 3 replaces them with the new structure:

| Title | event_type | chapter | recurrence_rule | date (template anchor) | time | location | description |
|---|---|---|---|---|---|---|---|
| `St. Petersburg Chapter Biweekly` | `chapter_recurring` | `St. Petersburg, FL` | `first_and_last_thursday_monthly` | Next 1st Thursday of current month | `6:30 PM EST` | `The Temple, 155 8th Street North, Saint Petersburg, FL 33701` | Sovereign Society's St. Petersburg chapter biweekly meetup. The 1st and last Thursday of every month. Brotherhood, accountability, and discussion. Open to all members. |
| `Thursday Group Lunch` | `weekly_recurring` | `Global` | `every_thursday` | Next Thursday | (left blank — set per occurrence) | (left blank — set per occurrence) | Weekly Thursday group lunch. Time and location alternate each week — confirm via the specific Thursday's event card before showing up. |

The "alternating times and locations" requirement for the Group Lunch: when occurrences are auto-generated from the `every_thursday` template, each child Event row inherits the template's blank `time` and `location` fields. An admin (or a delegated chapter lead in a future phase) edits the specific occurrence to fill in that week's details. Do NOT try to rotate through a list of preset locations — keep the data model simple and let humans schedule each Thursday.

Delete the existing 3 events from prod DB during the migration (or via a one-shot data-migration script invoked from `_seed_content`'s startup). Their RSVPs (if any) are toast. Acceptable per Kashi: this is pre-real-traffic; no real members have RSVP'd.

### 2.7 What does NOT happen in this phase

- Do NOT build a general RRULE engine or accept arbitrary recurrence rules.
- Do NOT build chapter management (a Chapter model with admins, regional permissions, etc.) — `chapter` is just a string for now.
- Do NOT build calendar invite (.ics) attachments — that's Phase 4 work alongside the engagement automations.
- Do NOT build RSVP confirmation emails — Phase 4.
- Do NOT touch `lib/ghl.py` — engagement-tagging on event RSVP is Phase 4 scope.
- Do NOT modify any Phase 2 files (Space templates, `_seed_content`'s spaces section).

---

## Step 3 — Implementation

### 3.1 Schema migration

Generate a new Alembic migration. Add to `Event`:

```python
event_type = db.Column(db.String(40), nullable=False, default="official_one_off")
chapter = db.Column(db.String(100), nullable=True)
recurrence_rule = db.Column(db.String(60), nullable=False, default="none")
recurrence_parent_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=True, index=True)
is_recurrence_template = db.Column(db.Boolean, nullable=False, default=False)
```

Migration file: `flask db migrate -m "events: add type/chapter/recurrence fields"` then `flask db upgrade` locally. Verify the generated migration matches the intent (alembic auto-detection sometimes misses defaults — eyeball it).

For prod: Railway runs `flask db upgrade` automatically as the release command per `railway.json`, so no manual step needed.

### 3.2 Model validation

Add a `__init__`-level or `validates` hook on `Event` that rejects invalid `event_type` and `recurrence_rule`. Allowed values exactly:
- `event_type ∈ {"chapter_recurring", "weekly_recurring", "member_meetup", "official_one_off"}`
- `recurrence_rule ∈ {"none", "every_thursday", "first_and_last_thursday_monthly"}`

Use SQLAlchemy `@validates` decorator. Raise `ValueError` on anything else.

### 3.3 Recurrence generator

Add to `app.py` (or a new `lib/recurrence.py` if you'd rather isolate it — your call, but keep it small):

```python
def _generate_upcoming_occurrences(template, weeks_ahead=8):
    """Idempotently materialize the next N weeks of occurrences for a recurring template Event."""
    # ... weekday math, datetime arithmetic ...
    # ... query for existing children to skip duplicates ...
    # ... db.session.add(Event(...)) for each new occurrence ...
```

Implementation detail: for `first_and_last_thursday_monthly`, walk months from the template's anchor date forward, computing the 1st Thursday and last Thursday of each month within the `weeks_ahead` window.

Children inherit: title, description, time, location, chapter, host_id, cover_image, event_type. They differ in: date, recurrence_parent_id (set to template.id), is_recurrence_template (False), recurrence_rule (set to "none"). Time/location can be edited per-occurrence after generation.

### 3.4 `_seed_content()` event section rewrite

Replace the existing 3-event seed block with:

```python
# Wipe stale events from any earlier seed run (safe: pre-real-traffic, no real RSVPs)
stale_titles = ["Fire to Fire - St. Pete", "Sovereign Wealth Workshop", "Brotherhood Summit"]
for t in stale_titles:
    Event.query.filter_by(title=t).delete()
db.session.flush()

# Idempotent template seeding
def _seed_recurring_template(title, ...):
    existing = Event.query.filter_by(title=title, is_recurrence_template=True).first()
    if existing:
        return existing
    template = Event(
        title=title, description=..., date=..., time=..., location=...,
        host_id=admin_user_id,
        event_type=...,
        chapter=...,
        recurrence_rule=...,
        is_recurrence_template=True,
    )
    db.session.add(template)
    db.session.flush()
    return template

st_pete_template = _seed_recurring_template(
    title="St. Petersburg Chapter Biweekly",
    description="Sovereign Society's St. Petersburg chapter biweekly meetup. The 1st and last Thursday of every month. Brotherhood, accountability, and discussion. Open to all members.",
    date=<next first thursday of current month>,
    time="6:30 PM EST",
    location="The Temple, 155 8th Street North, Saint Petersburg, FL 33701",
    event_type="chapter_recurring",
    chapter="St. Petersburg, FL",
    recurrence_rule="first_and_last_thursday_monthly",
)

lunch_template = _seed_recurring_template(
    title="Thursday Group Lunch",
    description="Weekly Thursday group lunch. Time and location alternate each week. Confirm via the specific Thursday's event card before showing up.",
    date=<next thursday>,
    time="",
    location="",
    event_type="weekly_recurring",
    chapter="Global",
    recurrence_rule="every_thursday",
)

db.session.commit()

# Generate the next 8 weeks of occurrences for both templates
_generate_upcoming_occurrences(st_pete_template, weeks_ahead=8)
_generate_upcoming_occurrences(lunch_template, weeks_ahead=8)
db.session.commit()
```

The `<next first thursday>` and `<next thursday>` calculations: use `datetime.date.today()` and step forward.

### 3.5 Event list grouping (`/events`)

Modify the existing `/events` route in `phase3_routes.py` and template:

```python
@phase3.route("/events")
@login_required
@paywall_required
def events():
    # Generate upcoming occurrences cheaply on every list view (idempotent)
    from app import _generate_upcoming_occurrences  # or wherever it lives
    for template in Event.query.filter_by(is_recurrence_template=True).all():
        _generate_upcoming_occurrences(template, weeks_ahead=8)
    db.session.commit()
    
    today = date.today()
    upcoming_chapter = Event.query.filter(
        Event.is_recurrence_template == False,
        Event.event_type == "chapter_recurring",
        Event.date >= today
    ).order_by(Event.date).all()
    upcoming_weekly = Event.query.filter(
        Event.is_recurrence_template == False,
        Event.event_type == "weekly_recurring",
        Event.date >= today
    ).order_by(Event.date).all()
    upcoming_meetups = Event.query.filter(
        Event.is_recurrence_template == False,
        Event.event_type == "member_meetup",
        Event.date >= today
    ).order_by(Event.date).all()
    return render_template("events.html",
        upcoming_chapter=upcoming_chapter,
        upcoming_weekly=upcoming_weekly,
        upcoming_meetups=upcoming_meetups)
```

Update `templates/events.html` to render three sections:
1. **Chapter Events** — grouped by chapter heading (`St. Petersburg, FL`, etc.), then list events under each. If only one chapter exists today (St. Pete), still wrap in a heading for forward-compat.
2. **Thursday Group Lunch** — single section with the upcoming lunches (alternating times/locations shown per occurrence).
3. **Local Meetups** — member-uploaded events. Empty-state copy: "No local meetups posted yet. Got something coming up in your city? Post it." with a CTA button to `/events/create`.

Each event card shows: cover image (if set), title, chapter, date + time, location (or "TBD" if blank), going-count, "RSVP" button.

### 3.6 Event creation route

Modify `phase3_routes.create_event`:

```python
@phase3.route("/events/create", methods=["GET", "POST"])
@login_required
@paywall_required
def create_event():
    if request.method == "POST":
        # Server-side gate: non-admins can only create member_meetup
        if not current_user.is_admin:
            request.form = request.form.copy()
            request.form["event_type"] = "member_meetup"
            request.form["recurrence_rule"] = "none"
            request.form["chapter"] = request.form.get("chapter", "").strip() or None  # members can set their own city
            request.form["is_recurrence_template"] = False
        # ... existing creation logic ...
```

Update `templates/create_event.html`:
- Show all fields (title, description, date, time, location, cover_image, max_attendees, chapter) for everyone.
- Show `event_type` dropdown ONLY for `current_user.is_admin`. Default to `member_meetup` and hidden for non-admins.
- Show `recurrence_rule` dropdown ONLY for admins. Hidden / not submitted for members.

### 3.7 Event detail (`/events/<id>`)

Minor template update: if the event has a `recurrence_parent_id`, show a small "Part of: <template title> (recurring)" line above the date. Otherwise no change.

---

## Step 4 — What NOT to do

- Do NOT modify any Space-related files, templates, or `_seed_content`'s spaces section. Phase 2 owns that.
- Do NOT add calendar invite (.ics) generation. Phase 4.
- Do NOT add RSVP confirmation emails. Phase 4.
- Do NOT add a Chapter model. `chapter` is a string for now.
- Do NOT use Celery, APScheduler, or any background scheduler. Recurrence generation is on-demand on every `/events` GET (cheap, idempotent).
- Do NOT seed any "official one-off" events. The annual Brotherhood Summit is not in scope.
- Do NOT touch lib/ghl.py.

---

## Step 5 — Smoke tests

Local Flask, fresh DB:

1. `rm -f instance/abmc.db && python app.py &`. Wait 3 sec. Server boots without error.
2. `sqlite3 instance/abmc.db "SELECT title, event_type, chapter, recurrence_rule, is_recurrence_template, recurrence_parent_id, date FROM event ORDER BY id;"`:
   - 2 templates (`is_recurrence_template=True`, `recurrence_parent_id=NULL`)
   - ~16 occurrences for the Thursday lunch (8 weeks × 1/week)
   - ~4-5 occurrences for the St. Pete biweekly (8 weeks ÷ 2 weeks/month average)
3. Hit `/events` (logged in) → three sections render: Chapter Events / Thursday Group Lunch / Local Meetups.
4. Hit `/events/create` as the placeholder user (non-admin):
   - `event_type` dropdown is hidden (or only shows "Local Meetup")
   - `recurrence_rule` is hidden
   - Submit a meetup with title "Austin Sunday Hike" → redirects to `/events`, the meetup appears under Local Meetups.
5. Hit `/events/create` as an admin:
   - All fields visible
   - Can create a `chapter_recurring` event for a new chapter (e.g. "Austin, TX", `first_and_last_thursday_monthly`) → 4-5 occurrences appear in Chapter Events.
6. Try to bypass the gate as non-admin: POST to `/events/create` with `event_type=chapter_recurring` in the form body. Server should force it to `member_meetup` (the gate runs server-side, not just on hidden form fields).
7. RSVP flow on a recurring occurrence: click going on next Thursday's lunch → `EventRSVP` row created with `event_id=<occurrence_id>` (NOT `template.id`). Going-count increments. Smoke pass.
8. Validation: in `flask shell`:
   ```python
   from models import Event, db
   e = Event(title="x", description="x", date=date.today(), event_type="not_a_real_type")
   db.session.add(e)
   db.session.commit()
   ```
   Should raise `ValueError: invalid event_type`. Same for invalid `recurrence_rule`.
9. Idempotency: `python app.py` twice. Second boot does NOT duplicate templates or occurrences.

Production verification (after deploy):

10. Hit prod `/events` (logged in as Bryce or Kashi after signup). Confirm three sections, St. Pete chapter biweekly with The Temple address, Thursday lunch occurrences. No "Fire to Fire", "Sovereign Wealth Workshop", or "Brotherhood Summit" anywhere — they were wiped.

---

## Step 6 — Update SoT

In `INTEGRATION-SOURCE-OF-TRUTH.md`:

- **§3 App Scope** — extend the `Events + RSVPs` line to mention chapters, recurrence, and member meetups.
- **§5 Environment Variables** — no changes (no new env vars).
- **§8 Phase Status** — add Phase 3 row, mark ✅ done with commit SHA.
- **§9 Decisions Log** — append a Phase 3 entry: schema additions, vocabulary lock for event_type and recurrence_rule, recurrence-generation strategy (per-occurrence rows from template, idempotent on-demand on `/events` GET), member meetup permission gate, locked seed content (St. Pete biweekly @ The Temple, Thursday Group Lunch), explicit deletion of the old 3 seeded events.
- **§10 Risks** — append: "Recurrence generation runs on every `/events` GET. Cheap (idempotent existence check) but at high traffic this becomes a measurable DB cost. If `/events` traffic exceeds ~10 req/sec sustained, move generation to a Railway cron."

---

## Step 7 — Commit + push

Three commits, atomic:

**Commit 1 — schema + model validation:**
```
phase-3: events schema — type/chapter/recurrence fields + validation

- migration <revid>_events_type_chapter_recurrence
- @validates on event_type and recurrence_rule with locked vocabulary
- recurrence_parent_id FK + is_recurrence_template flag for occurrence rows
```
Stage exactly: `models.py`, `migrations/versions/<new>.py`.

**Commit 2 — recurrence generator + seed rewrite:**
```
phase-3: seed st. pete biweekly + thursday lunch + recurrence generator

- _generate_upcoming_occurrences helper (8 weeks ahead, idempotent)
- replaces the 3 stale seed events with the 2 recurring templates
- wipes old "Fire to Fire", "Sovereign Wealth Workshop", "Brotherhood Summit" rows
- generator called from _seed_content and from /events GET on every request
```
Stage exactly: `app.py`.

**Commit 3 — routes + templates + sot:**
```
phase-3: events tab — three sections + member meetup creation

- /events groups by chapter_recurring / weekly_recurring / member_meetup
- /events/create opens to active members, gates type/recurrence to admins
- event_detail shows recurrence-parent line if applicable
- sot updated: §3 app scope, §8 phase status, §9 decisions, §10 risks
```
Stage exactly: `phase3_routes.py`, `templates/events.html`, `templates/create_event.html`, `templates/event_detail.html`, `INTEGRATION-SOURCE-OF-TRUTH.md`.

Push after each commit (or batch — either way fine).

---

## Step 8 — Report back to manager

7-bullet summary:

1. **Schema** — migration revid, fields added, validates working.
2. **Recurrence generator** — 8-week window, idempotent verified by smoke test 9.
3. **Seed** — old 3 events wiped; 2 templates created (St. Pete biweekly @ The Temple + Thursday lunch); occurrence counts after first boot.
4. **Permissions** — member meetup creation works; admin-only fields hidden client-side AND gated server-side (smoke 6).
5. **UI** — three sections render correctly; empty states for chapters/meetups.
6. **Live verification** — prod `/events` shows the new structure, no stale events visible.
7. **Surprises / new launch blockers** — anything that demands a manager decision (e.g. chapter empty-state copy needs revision, RSVPs to old events surface inconsistently, recurrence generator hit a date edge case at month boundaries).

If anything in this prompt is genuinely ambiguous OR you discover an architectural question (e.g. RSVPs on old events you weren't told about; a separate "Featured Events" UI exists somewhere; the date math at year-end has a bug; etc.), STOP and report — do NOT decide.
