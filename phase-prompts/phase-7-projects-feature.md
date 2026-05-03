# Phase 7 — Sovereign Society Projects feature

> Paste into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Goal:** introduce a Projects feature where members publish what they're building, other members browse and express interest, and progress gets logged over time.
>
> ⚠️ **MANAGER ASSUMPTIONS (Kashi to confirm before firing this prompt).** Kashi mentioned "we need to introduce this feature" without further spec. The manager session has scoped what makes sense given the brand and existing models. **Read `## Step 2 — Decisions assumed` carefully and CONFIRM with Kashi before executing.** If any assumption is wrong, the manager rewrites this prompt before it fires.

---

## ⚠️ Pre-execution checklist (manager session does this BEFORE handing the prompt over)

The executor should NOT start until Kashi has confirmed in the manager chat:

- [ ] Projects are **personal builds** (businesses, products, missions) — not transactional opportunities (those go in `Deal`)
- [ ] Members own their projects; can list 0–N projects
- [ ] Projects show on a project's creator's profile AND in a global `/projects` feed
- [ ] Other members can express interest, follow updates, and (optionally) be added as collaborators
- [ ] Projects are NOT a substitute for Spaces; Spaces are topic-based group conversation, Projects are individual-owned with discrete state

If any of these is wrong, manager rewrites § 2 below before sending to executor.

---

## Step 0 — Pull + read

```bash
git fetch origin && git status
```

---

## Step 1 — Read first

1. `INTEGRATION-SOURCE-OF-TRUTH.md`.
2. `models.py` — pay attention to `Deal`, `Win`, `Post`, `Space` for boundary clarity. Projects are different from all four.
3. `templates/deals.html` and `templates/deal_detail.html` — closest existing UX precedent (member-created listings + interest expression + detail view). Lift design patterns; don't copy logic verbatim.
4. `features_routes.py` — Deal routes (create / detail / interest) for the route shape pattern.

---

## Step 2 — Decisions assumed (manager flags for Kashi confirmation)

### 2.1 Project model

```python
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500), default="")  # one-liner shown in feed cards
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(40), nullable=False, default="building")  # idea / building / launching / scaling / paused
    project_type = db.Column(db.String(40), nullable=False, default="business")  # business / build / mission / cause / product
    looking_for = db.Column(db.String(100), default="")  # free-text, e.g. "co-founder, capital, customers"
    cover_image = db.Column(db.String(300), default=None)
    visibility = db.Column(db.String(20), nullable=False, default="members_only")  # members_only / brotherhood_only (Lifetime+) / private
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship("User", backref="projects")
    interests = db.relationship("ProjectInterest", backref="project", lazy=True, cascade="all, delete-orphan")
    updates = db.relationship("ProjectUpdate", backref="project", lazy=True, cascade="all, delete-orphan", order_by="ProjectUpdate.created_at.desc()")

class ProjectUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(300), default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User")

class ProjectInterest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("project_id", "user_id", name="unique_project_interest"),)
```

### 2.2 Locked vocabularies

`status` ∈ `{idea, building, launching, scaling, paused}`. Validated via `@validates` on the model.

`project_type` ∈ `{business, build, mission, cause, product}`. Where:
- `business` = revenue-generating venture
- `build` = technical/physical thing being constructed (could be a product, a homestead, a prototype)
- `mission` = personal goal with social/spiritual stakes (not necessarily commercial)
- `cause` = advocacy / community
- `product` = single-product builder (vs full company)

`visibility` ∈ `{members_only, brotherhood_only, private}`:
- `members_only` (default): visible to any active subscriber/lifetime member
- `brotherhood_only`: visible only to `lifetime_access=True` members (gated tier)
- `private`: only the creator + invited collaborators (Phase 7+ feature, hidden in this phase's UI)

### 2.3 Routes

- `GET /projects` — global feed, sorted by `updated_at desc`. Filterable by `status` + `project_type` (querystring). Respects visibility.
- `GET /projects/<id>` — detail. Shows project, updates timeline, interest list, "Express interest" button.
- `GET /projects/create` — form (members only).
- `POST /projects/create` — create.
- `GET /projects/<id>/edit` — only by creator.
- `POST /projects/<id>/edit` — update.
- `POST /projects/<id>/interest` — current user expresses interest. Idempotent (re-clicking removes interest, like the existing `Deal.interests` toggle).
- `POST /projects/<id>/update` — creator posts a progress update. Other members CANNOT post updates here (use the comment-thread pattern from `Post` if you want member discussion — but DO NOT add that in this phase, scope creep).
- `POST /projects/<id>/archive` — creator marks `is_active=False` (soft delete, hide from feed).

All routes are `@login_required @paywall_required`.

### 2.4 Profile integration

User profile (`/profile/<id>`) gets a "Projects" section showing the user's active projects. Cards link to `/projects/<id>`.

### 2.5 Checklist integration

Optional 8th checklist item (NOT shipping in this phase, but design to support): "Post a project — share what you're building." Slug `post-project`. If it's added, auto-check fires on first `Project` creation via the slug-based helper from Phase 4.

### 2.6 What does NOT happen here

- Do NOT add the checklist item (Phase 4's checklist is final at 7 items; if Kashi wants Projects in the list, that's a Phase 4.1 follow-up).
- Do NOT integrate with GHL (no engagement-tagging on project create — Phase 8 territory).
- Do NOT add notifications (e.g. "X expressed interest in your project") — Phase 8.
- Do NOT add direct messaging hooks ("Message this builder") — wire later if needed; the existing DM feature works once both members exist.
- Do NOT seed any sample projects. Projects are member-created from day one.
- Do NOT add a Project category to the Deal Board (Deals stay separate — different model, different intent).

---

## Step 3 — Implementation

### 3.1 Schema migration

Generate via `flask db migrate -m "projects: add Project + ProjectUpdate + ProjectInterest"`. Verify the auto-detection caught:
- 3 new tables
- All FKs
- The unique constraint on `ProjectInterest`
- Indexes on `project.user_id`, `project_update.project_id`, `project_interest.project_id`

### 3.2 Routes

In `features_routes.py`. Pattern-match the existing Deal routes for shape (form rendering, validation, redirect on success).

### 3.3 Templates

New files:
- `templates/projects.html` — feed
- `templates/project_detail.html` — detail w/ updates timeline + interests
- `templates/create_project.html` — form
- `templates/edit_project.html` — same shape as create

Card design: lift the brand patterns from `templates/deals.html` (dark bg, gold accents, cover image at top, status pill, type tag, "looking for" text, interest count + button). Don't copy CSS classes — make new ones (`.project-card`, etc.) so future divergence doesn't entangle.

### 3.4 Nav

Add "Projects" to the main nav (and mobile menu) between "Deals" and "Resources".

### 3.5 Validation

`@validates("status")` on Project: must be in the locked set.  
`@validates("project_type")`: same.  
`@validates("visibility")`: same.

`title` required, max 200 chars.  
`summary` max 500.  
`description` no max (TEXT).  
`looking_for` max 100.

### 3.6 Visibility enforcement

In all read routes (feed + detail), filter:
```python
def _visible_projects(query, current_user):
    if current_user.lifetime_access:
        return query.filter(Project.visibility != "private", Project.is_active == True)
    if current_user.has_active_subscription:
        return query.filter(Project.visibility == "members_only", Project.is_active == True)
    return query.filter(False)  # paywall, but @paywall_required already blocks
```

Self-view exception: a user always sees their own projects regardless of visibility.

---

## Step 4 — What NOT to do

- Do NOT extend Deal/Post/Win models. Project is a sibling, not a refactor.
- Do NOT add image-cropping / profile-banner / cover-image-template features. Cover image is just a single upload field.
- Do NOT add comments on ProjectUpdate (creator-posts-only model is intentional for v1).
- Do NOT add any analytics, view-counts, or trending logic.
- Do NOT touch other phases' files.

---

## Step 5 — Smoke tests

1. Migration applies clean. 3 new tables, all relationships work in `flask shell`.
2. Validates: creating a Project with `status="invalid"` raises ValueError.
3. Member A creates a project (`/projects/create`) → appears on `/projects` feed → appears on Member A's `/profile/<a_id>` → not duplicated.
4. Member B opens the project detail → "Express interest" button → click → POST /interest → ProjectInterest row created. Toggle behavior: re-click → row deleted.
5. Member A posts a ProjectUpdate → appears in detail page's update timeline. Member B cannot POST to /update for that project (403 server-side).
6. Member B with `has_active_subscription=True` (no lifetime) attempts to view a `brotherhood_only` project → 404 (or filter-out from feed). Member C with `lifetime_access=True` sees it.
7. Archive: creator hits archive → project disappears from public feeds but is reachable by direct URL `/projects/<id>` for the creator (status banner: "Archived"). All others get 404.
8. No GHL pushes fire (verify by grepping for `ghl.upsert_contact` from any new route — should be zero).
9. Projects nav link visible after deploy. Empty `/projects` feed renders empty state ("No projects yet. Be the first to share what you're building.").
10. Cross-feature integrity: existing Spaces, Deals, Wins, Feed unaffected. Run their basic flows.

---

## Step 6 — Update SoT

- §3 App Scope: add "Projects" entry under "Member-to-Member" alongside Deals.
- §8 Phase Status: Phase 7 ✅ done.
- §9 Decisions: log vocab locks (status, project_type, visibility), boundary with Deal/Win/Space, what's deferred (notifications, comments, GHL).
- §10 Risks: visibility tiers introduce a new gating surface; if Brotherhood-tier visibility leaks (a non-Lifetime member sees a brotherhood_only project), that's a privacy bug worth grep-checking on every change to project read paths.

---

## Step 7 — Commit + push

Three commits:

**Commit 1 — schema:**
```
phase-7: project + project_update + project_interest models + migration
```

**Commit 2 — routes + visibility helper:**
```
phase-7: /projects feed + detail + create/edit + interest + update routes

- visibility tiers: members_only / brotherhood_only / private
- @validates locks status/project_type/visibility vocab
- toggle-interest (idempotent), creator-only updates, soft-archive
```

**Commit 3 — templates + nav + sot:**
```
phase-7: projects ui + nav entry + sot
```

---

## Step 8 — Report back

5 bullets: schema, vocab validation, visibility gating verified, ui matches design system, surprises.

If Kashi flags any of the §2 assumptions as wrong before this phase fires, STOP — the manager rewrites the prompt and re-issues. Don't ship a version Kashi won't approve.
