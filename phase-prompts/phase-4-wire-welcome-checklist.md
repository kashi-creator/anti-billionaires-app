# Phase 4 — Wire the welcome checklist (buttons function + auto-completion)

> Paste this entire prompt into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Goal:** the post-signup welcome checklist buttons currently link to the wrong pages (or nowhere meaningful) and don't auto-complete when the user actually does the action. Fix both.
>
> Surfaced 2026-05-03 by manager session. Live state: `seed_checklist()` in `phase3_routes.py` defines 5 items, "Read the Manifesto" links to `/feed` (no actual manifesto page exists), "RSVP to Fire to Fire" references an event that's being wiped by Phase 3.
>
> Runs in parallel with Phase 2 and Phase 3 (mostly disjoint, with one touchpoint: this phase's "RSVP to an event" item references the new Phase-3 event types).

---

## Step 0 — Pull before reading

```bash
git fetch origin && git status
```
Reset hard if behind: `git reset --hard origin/main`.

---

## Step 1 — Read first

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — full file.
2. `phase3_routes.py` lines ~190–270: `welcome()`, `check_item()`, `_auto_check_item()`, `seed_checklist()`.
3. `templates/welcome.html` and `templates/feed.html` lines 211–240 (sidebar checklist card).
4. `app.py` route `/feed` (handler `feed`): the part where `checklist` + `checklist_all_done` + `checklist_pct` get computed for the sidebar.
5. `templates/landing.html` lines 575–585 (the manifesto block — "engineered reality" → "build the fire"). You'll lift this copy into the new `/manifesto` page.
6. `features_routes.py`: locate the handlers for `create_post`, `join_space`, `toggle_follow`, `event_rsvp`, `complete_lesson`. Each needs an `_auto_check_item(...)` call.

---

## Step 2 — Decisions locked

### 2.1 Final checklist (locked)

| Order | Title | Description | Link | Auto-check trigger |
|---|---|---|---|---|
| 1 | Complete your profile | Add a photo and bio so the brotherhood knows who you are. | `/profile/edit` | When `User.profile_photo` is non-null AND `User.bio` is non-empty |
| 2 | Read the Manifesto | The founding manifesto. Read it before anything else. | `/manifesto` | On GET of `/manifesto` (sets the flag for the viewing user) |
| 3 | Make your first post | Drop into the feed. Who you are, what you're building, what you need. | `/feed` (with `?focus=composer` so the JS opens the post composer on load) | When user creates their 1st `Post` row |
| 4 | Join a Space | Pick a Space that fits you and join the conversation. | `/spaces` | When user has ≥1 `SpaceMembership` |
| 5 | Follow 3 brothers | Connect with other members. Build your circle. | `/members` | When user has ≥3 `Follow` rows where `follower_id == user.id` |
| 6 | RSVP to an event | Show up. Whether it's a chapter biweekly or a member meetup, get in the room. | `/events` | When user has ≥1 `EventRSVP` with `status="going"` |
| 7 | Complete a lesson | Open The Vault and finish your first lesson. | `/lessons` | When user has ≥1 `LessonProgress` with `completed=True` |

Item 1 is NEW. Items 2 (link), 3 (renamed + new link param), 4 (renamed + relaxed threshold to 1), 5 (renamed + relaxed threshold to 3), 6 (renamed + decoupled from the wiped "Fire to Fire" event), 7 is NEW.

### 2.2 Manifesto page

A new `/manifesto` route and `templates/manifesto.html`. **Lift the copy from `landing.html` lines ~575–585** (the manifesto block: "engineered reality" / "reclamation of masculine power" / "build the fire"). Don't paraphrase. The landing-page voice is canonical — copy verbatim.

Layout: full-page reading experience, NOT extending `base.html` (or extending it but with the post-login chrome). Your call — match whichever is closer to the existing premium feel. Wrap the manifesto text in a centered narrow column (max-width ~720px), serif, generous line height. Black background, gold accent on key phrases. No nav distractions.

Bottom of the page: a single "Back to the Society" button → `/feed`.

### 2.3 Auto-check semantics

- The auto-check function is idempotent — calling it on an already-completed item is a no-op.
- The `_auto_check_item` matches by case-insensitive `LIKE` on title substring. This is fragile (renaming an item breaks the auto-check). **Strengthen it:** change the helper to take an explicit `slug` argument that maps to a single canonical item, with the slug stored as a new `ChecklistItem.slug` column (unique). Slug values: `complete-profile`, `read-manifesto`, `first-post`, `join-space`, `follow-brothers`, `rsvp-event`, `complete-lesson`.
- Add a tiny migration to create the `slug` column (nullable) and a `seed_checklist()` upgrade path that backfills slug on existing items by title match (one-time on next boot).

### 2.4 What does NOT happen here

- Do NOT modify the welcome route, template structure, or sidebar widget design — only the underlying data + links + auto-checks.
- Do NOT add gamification points for completing checklist items (the existing `User.points` system stays as-is).
- Do NOT add notifications when items auto-complete (Phase 6 territory).
- Do NOT touch Phase 2 (Space cover images) or Phase 3 (event types) files.

---

## Step 3 — Implementation

### 3.1 Schema

Migration: add `slug` to `ChecklistItem`:
```python
slug = db.Column(db.String(60), unique=True, nullable=True)
```
Unique constraint, nullable so existing rows pass during the migration window. Backfill via `seed_checklist()` on boot.

### 3.2 `seed_checklist()` rewrite

Replace the existing function. New version:

```python
def seed_checklist():
    desired = [
        ("complete-profile",  "Complete your profile",  "Add a photo and bio so the brotherhood knows who you are.", "/profile/edit"),
        ("read-manifesto",    "Read the Manifesto",     "The founding manifesto. Read it before anything else.",     "/manifesto"),
        ("first-post",        "Make your first post",   "Drop into the feed. Who you are, what you're building, what you need.", "/feed?focus=composer"),
        ("join-space",        "Join a Space",           "Pick a Space that fits you and join the conversation.",     "/spaces"),
        ("follow-brothers",   "Follow 3 brothers",      "Connect with other members. Build your circle.",            "/members"),
        ("rsvp-event",        "RSVP to an event",       "Show up. Whether it's a chapter biweekly or a member meetup, get in the room.", "/events"),
        ("complete-lesson",   "Complete a lesson",      "Open The Vault and finish your first lesson.",              "/lessons"),
    ]
    changed = False
    for i, (slug, title, desc, link) in enumerate(desired):
        # Look up by slug first; fall back to title for backfill of legacy rows
        existing = ChecklistItem.query.filter_by(slug=slug).first() or \
                   ChecklistItem.query.filter_by(title=title).first()
        if existing:
            # Self-heal: backfill slug, update link/desc/title/order if drifted
            existing.slug = slug
            existing.title = title
            existing.description = desc
            existing.link = link
            existing.order_index = i
        else:
            db.session.add(ChecklistItem(slug=slug, title=title, description=desc, link=link, order_index=i))
        changed = True
    # Wipe the legacy "RSVP to Fire to Fire" if still around
    legacy = ChecklistItem.query.filter(ChecklistItem.title.ilike("%fire to fire%")).first()
    if legacy:
        UserChecklist.query.filter_by(item_id=legacy.id).delete()
        db.session.delete(legacy)
        changed = True
    if changed:
        db.session.commit()
```

### 3.3 New `_check_item_by_slug` helper

Replace `_auto_check_item(user_id, title_substring)` with `_check_item_by_slug(user_id, slug)` that uses the slug column. Keep the old function as a thin shim if existing callers reference it (grep first), so this phase doesn't break anything that pre-existed.

### 3.4 Auto-check call sites

Add or verify `_check_item_by_slug` calls in these handlers (find each, add the call right before the response):

| File:function | Trigger | Slug |
|---|---|---|
| `app.py:create_post` | After successful post insert | `first-post` |
| `app.py:edit_profile` | After profile save IF `bio` and `profile_photo` are both populated | `complete-profile` |
| `app.py:join_space` | After SpaceMembership insert IF user has ≥1 total | `join-space` |
| `app.py:toggle_follow` (the follow-add branch only) | After Follow insert IF user has ≥3 follows | `follow-brothers` |
| `phase3_routes.event_rsvp` | After EventRSVP insert/update IF status=="going" | `rsvp-event` |
| `phase3_routes.complete_lesson` | After LessonProgress upsert with completed=True | `complete-lesson` |

For `read-manifesto`: the auto-check fires inside the new `/manifesto` GET handler.

For `complete-profile`: the trigger is "both bio AND profile_photo present." Implementation: in `edit_profile` POST handler after `db.session.commit()`, check `if current_user.bio and current_user.profile_photo: _check_item_by_slug(...)`. ALSO call this from `onboarding_submit` if the user completes the photo+bio steps via the onboarding flow.

### 3.5 New `/manifesto` route + template

Add to `app.py` (kept alongside other public-ish routes; gated behind `@login_required` since the checklist is post-signup):

```python
@app.route("/manifesto")
@login_required
@paywall_required
def manifesto():
    _check_item_by_slug(current_user.id, "read-manifesto")
    return render_template("manifesto.html")
```

Create `templates/manifesto.html`. Lift the copy from `landing.html` manifesto block. Wrap in a centered reading column. Match brand: `#0A0A0A` bg, `#D4AF37` accent, Cormorant Garamond or Fraunces serif headings, generous spacing.

### 3.6 Feed composer focus

`/feed?focus=composer` — pass the query param to the template, JS reads it on load and auto-focuses (or auto-opens, if the composer is collapsed) the post-creation widget. Existing JS hook in `templates/feed.html` or `static/js/app.js` — find the post-composer init and add a 5-line check.

### 3.7 Sidebar widget

The feed sidebar shows up to N items from the checklist. Verify the existing logic at `app.py:feed` correctly recomputes `checklist_pct` from the new 7-item list. If the existing logic is "first 5 incomplete items," consider whether 7 items in the sidebar is too many — if so, cap at 5 and link "See all" to `/welcome`.

---

## Step 4 — What NOT to do

- Do NOT change the visual design of the checklist widget (sidebar card or `/welcome` page).
- Do NOT remove any existing route or model.
- Do NOT introduce a new background job to recompute auto-completion across all users — auto-checks fire inline on the action.
- Do NOT touch `lib/ghl.py`.
- Do NOT touch event types or recurrence (Phase 3 owns).

---

## Step 5 — Smoke tests

Local Flask:

1. Fresh DB → boot → `flask shell` → `ChecklistItem.query.count()` returns 7. All have non-null slugs.
2. Existing DB with legacy rows ("RSVP to Fire to Fire" present) → boot → legacy row deleted, all 7 canonical rows present, slugs populated.
3. Sign up a fresh user → hit `/feed` → sidebar shows 7 items, all unchecked, `checklist_pct=0`.
4. Hit `/manifesto` → page renders the manifesto, "Read the Manifesto" item flips to ✓ in `/welcome`.
5. Edit profile, add photo + bio, save → "Complete your profile" flips to ✓.
6. Post in feed → "Make your first post" flips to ✓.
7. Join a Space → "Join a Space" flips to ✓.
8. Follow 1 member → "Follow 3 brothers" stays unchecked. Follow 2 more → flips to ✓ at the 3rd.
9. RSVP `going` to any event → "RSVP to an event" flips to ✓.
10. Complete a lesson → "Complete a lesson" flips to ✓.
11. All 7 done → `checklist_all_done=True` → sidebar widget hides on next `/feed` GET.

Production verification (after deploy):

12. Hit prod `/manifesto` (logged in) → renders correctly, slug-based auto-check works.

---

## Step 6 — Update SoT

- §3 App Scope: extend "Onboarding Checklists" line to mention manifesto + auto-completion.
- §8 Phase Status: add Phase 4 row, ✅ done with commit SHA.
- §9 Decisions Log: append Phase 4 entry — locked checklist (7 items with slugs), manifesto route + verbatim copy lift from landing, slug-based auto-completion vs old title-substring matching.
- §10 Risks: no new risks.

---

## Step 7 — Commit + push

Two commits:

**Commit 1 — schema + slug-based auto-check + checklist seed rewrite:**
```
phase-4: checklist slugs + 7-item lock + slug-based auto-completion

- migration adds ChecklistItem.slug (unique, nullable for backfill)
- seed_checklist rewritten with 7 canonical items + auto-backfill slug on
  existing rows by title match
- legacy "RSVP to Fire to Fire" item deleted in same boot pass
- _check_item_by_slug replaces title-substring _auto_check_item
- auto-check call sites added in: create_post, edit_profile,
  onboarding_submit, join_space, toggle_follow, event_rsvp, complete_lesson
```
Stage exactly: `models.py`, `migrations/versions/<new>.py`, `phase3_routes.py`, `app.py`, `features_routes.py`.

**Commit 2 — manifesto page + sot:**
```
phase-4: /manifesto route + sot — verbatim copy lift from landing
```
Stage exactly: `app.py` (route addition), `templates/manifesto.html`, `INTEGRATION-SOURCE-OF-TRUTH.md`.

Push.

---

## Step 8 — Report back to manager

5-bullet summary:

1. **Schema** — migration revid, slug column, all 7 items have unique slugs.
2. **Seed self-heal** — old title-only items got slugs backfilled; legacy "Fire to Fire" item deleted; verified count=7 in prod after deploy.
3. **Auto-checks** — list of files+functions where slug-based checks fire; each smoke 4-10 passes.
4. **Manifesto page** — route + template shipped; copy lifted verbatim from landing.html.
5. **Surprises / blockers** — anything found (e.g. a checklist item being rendered hardcoded somewhere, the sidebar widget breaking with 7 items, `/feed?focus=composer` JS hook missing).

If anything is genuinely ambiguous OR you find a different checklist-related model elsewhere, STOP and report.
