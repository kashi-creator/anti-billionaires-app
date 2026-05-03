# Phase 5 — Member Self-Assessment (8 pillars × 5 Likert) + insert into onboarding

> Paste into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Goal:** every new member completes a 40-question self-assessment across the 8 Sovereign Code pillars BEFORE they enter the existing 5-step onboarding (profile photo → bio → location → spaces → first post). Scores are stored per-pillar and re-takeable from the profile.
>
> Full question text + scoring scale lives in memory at `~/.claude/projects/-Users-kenneth-anti-billionaires-app/memory/project_pending_assessment_feature.md`. **Read that file first.** It's the source of truth for the 8 pillars and the exact 40 question strings — quote verbatim, do not paraphrase.

---

## Step 0 — Pull + read memory

```bash
git fetch origin && git status
cat ~/.claude/projects/-Users-kenneth-anti-billionaires-app/memory/project_pending_assessment_feature.md
```

Reset hard if behind. Read the assessment memory file in full.

---

## Step 1 — Read first

1. `INTEGRATION-SOURCE-OF-TRUTH.md`.
2. The assessment memory file (above).
3. `models.py` — `User` model. `Onboarding` flag at `onboarding_complete`. You'll add an analogous `assessment_complete` field.
4. `app.py` routes: `subscription_success` (around line 1346), `signup_with_code` (the route added by Phase 0C, around line 825). After successful account creation in either, the redirect target needs to change from `/welcome` (or `/onboarding`) → `/assessment`.
5. `phase3_routes.py` — `welcome()` and `onboarding()`. Reference patterns for multi-step Jinja flows.
6. `templates/onboarding.html` — visual style + step progression component (the gold dotted progress dots). The assessment page should match this aesthetic.

---

## Step 2 — Decisions locked

### 2.1 8 pillars, 5 questions each (verbatim from memory file)

Pillar order locked (this becomes the display + slug order):
1. PURPOSE
2. STRENGTH
3. WEALTH
4. BROTHERHOOD
5. FAMILY
6. FAITH
7. AWARENESS
8. CONTROL

Each pillar has exactly 5 Likert questions. Quote them VERBATIM from the memory file. Do not edit, paraphrase, reorder, or rewrite. The pillar names match the locked landing-page edits in `project_pending_landing_edits.md` — assessment and landing must stay in lockstep.

### 2.2 Likert scale (verbatim)

```
1 = Not at all
2 = Rarely
3 = Sometimes
4 = Most of the time
5 = Completely
```

Default selection: none (force the user to pick — don't pre-select 3 or any default). Required to submit each pillar.

### 2.3 UI flow

8 pages total, one pillar per page. Each page shows:
- Pillar name as the page title (e.g. "PILLAR 1 / PURPOSE")
- 5 questions, each with the 5-radio Likert scale below it
- Progress indicator at top: dots (8 dots, current pillar gold, completed pillars gold-dimmed, future grey)
- "Continue" button at bottom (disabled until all 5 questions are answered)
- "Skip assessment for now" link in the footer (small grey text, the only way out)

After pillar 8 submission: a results page showing the 8 pillar scores (1.0–5.0 each, one decimal), with a "Begin onboarding" CTA → `/onboarding` (the existing 5-step flow).

### 2.4 Schema

New model `AssessmentResponse`:
```python
class AssessmentResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    answers_json = db.Column(db.Text, nullable=False)  # JSON: {"purpose": [3,4,5,2,3], "strength": [...], ...}
    pillar_scores_json = db.Column(db.Text, nullable=False)  # JSON: {"purpose": 3.4, "strength": 2.6, ...}

    user = db.relationship("User", backref="assessment_responses")
```

A user can have multiple `AssessmentResponse` rows over time (re-takes are tracked, never overwritten). Latest row is "current."

Add to `User`:
```python
assessment_complete = db.Column(db.Boolean, nullable=False, default=False)
```
Set true after first submission.

### 2.5 Skip behavior

The "Skip assessment for now" link sets `assessment_complete=True` on the User (so they're not nagged forever) but does NOT create an `AssessmentResponse` row. Users who skipped can revisit via `/assessment` from their profile and submit later — the skip is just a "I'll do it later" not a permanent opt-out.

The profile page gets a small "Take/retake the assessment" link in the future. For this phase, just expose `/assessment` as a re-callable route — profile UI integration is out of scope.

### 2.6 Insertion point in signup flow

After Stripe checkout success (`/subscription/success`) AND after founder-code signup (`/signup-with-code`), the redirect target changes from the current target → `/assessment` IF `not current_user.assessment_complete`, ELSE → existing redirect target.

Implementation: add a small helper `_post_signup_redirect(user)` that:
1. If `not user.assessment_complete` → return `redirect(url_for('assessment'))`
2. Else if `not user.onboarding_complete` → return `redirect(url_for('onboarding'))`
3. Else → return `redirect(url_for('feed'))`

Called from `/subscription/success` after the new user is created/logged in, AND from `/signup-with-code` after `login_user(user, remember=True)`.

Final assessment results page CTA → `/onboarding` (start step 1: profile photo).

### 2.7 What does NOT happen here

- Do NOT compute matching, recommendations, or content based on scores. Pillar scores feed nothing yet — they're just stored and displayed.
- Do NOT show pillar scores publicly to other members (private to the user).
- Do NOT integrate with leveling/tier system (`User.points` etc.). Out of scope.
- Do NOT add charts/graphs (display scores as plain numbers — `4.2 / 5`).
- Do NOT add localization or i18n.
- Do NOT touch other phases' files (Spaces, Events, Checklist).

---

## Step 3 — Implementation

### 3.1 Migration

```python
# add_assessment_models.py
op.add_column("user", sa.Column("assessment_complete", sa.Boolean(), nullable=False, server_default=sa.false()))
op.create_table("assessment_response",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True),
    sa.Column("submitted_at", sa.DateTime, nullable=False),
    sa.Column("answers_json", sa.Text, nullable=False),
    sa.Column("pillar_scores_json", sa.Text, nullable=False),
)
op.create_index("ix_assessment_response_user_id", "assessment_response", ["user_id"])
```

### 3.2 Question data

A `lib/assessment.py` (NEW file) module exposing:
```python
PILLARS = [
    {"slug": "purpose",     "name": "Purpose",     "questions": [...5 verbatim strings from memory...]},
    {"slug": "strength",    "name": "Strength",    "questions": [...]},
    # ... 6 more
]
LIKERT = [
    {"value": 1, "label": "Not at all"},
    {"value": 2, "label": "Rarely"},
    {"value": 3, "label": "Sometimes"},
    {"value": 4, "label": "Most of the time"},
    {"value": 5, "label": "Completely"},
]
```
All 40 question strings copied directly from memory. Centralized so future content changes are one-file.

### 3.3 Routes

```python
@app.route("/assessment")
@login_required
@paywall_required
def assessment():
    # Resume in-progress (sessionstorage on client) or start at pillar 1
    return render_template("assessment.html", pillars=PILLARS, likert=LIKERT)

@app.route("/assessment/submit", methods=["POST"])
@login_required
@paywall_required
@require_csrf
def assessment_submit():
    # Body: { "answers": { "purpose": [3,4,5,2,3], ... 8 pillars ... } }
    # Validate: 8 keys, each is array of 5 ints in 1..5
    # Compute pillar averages, write AssessmentResponse, flip user.assessment_complete=True
    # Return JSON { "redirect": "/assessment/results", "scores": {...} }

@app.route("/assessment/results")
@login_required
@paywall_required
def assessment_results():
    latest = AssessmentResponse.query.filter_by(user_id=current_user.id).order_by(AssessmentResponse.submitted_at.desc()).first()
    return render_template("assessment_results.html", response=latest, pillars=PILLARS)

@app.route("/assessment/skip", methods=["POST"])
@login_required
@paywall_required
@require_csrf
def assessment_skip():
    current_user.assessment_complete = True
    db.session.commit()
    return redirect(url_for("onboarding"))
```

### 3.4 Templates

`templates/assessment.html`: single-page progressive disclosure (8 sub-sections, hidden/shown via JS as user advances). Or one-page-per-pillar with an explicit POST submit at the end. **Recommend single-page with JS pagination** — simpler to validate "all 5 selected" client-side, single submit.

Layout matches `templates/onboarding.html` aesthetic: dark bg, gold accents, Cormorant Garamond serif headings, centered narrow column.

`templates/assessment_results.html`: 8 score rows (`Pillar Name — 4.2 / 5`), short "Where to go from here" copy, "Begin onboarding" CTA.

### 3.5 Redirect helper + integration

In `app.py` (not blueprint):
```python
def _post_signup_redirect(user):
    if not getattr(user, "assessment_complete", False):
        return redirect(url_for("assessment"))
    if not getattr(user, "onboarding_complete", False):
        return redirect(url_for("onboarding"))
    return redirect(url_for("feed"))
```

Replace the current redirect calls in:
- `subscription_success` after the user is fully created and logged in
- `signup_with_code` after `login_user(user, remember=True)` — currently returns `{"redirect": "/welcome"}` per Phase 0C's spec; change to `{"redirect": url_for_assessment_or_next(user)}` resolved server-side.

For `signup_with_code` (returns JSON), pre-resolve the URL string instead of using `_post_signup_redirect` (which returns a Flask Response). Helper variant:
```python
def _post_signup_redirect_url(user):
    if not user.assessment_complete: return url_for("assessment")
    if not user.onboarding_complete: return url_for("onboarding")
    return url_for("feed")
```

---

## Step 4 — What NOT to do

- Do NOT modify the existing 5-step onboarding flow or `/welcome` checklist. The assessment is a separate prepended flow, not an onboarding step.
- Do NOT delete or invalidate older `AssessmentResponse` rows on retake. History is data.
- Do NOT add an admin UI for inspecting member scores. Out of scope.
- Do NOT cross over into Phase 4 (welcome checklist), Phase 6 (location), or Phase 7 (projects) territory.

---

## Step 5 — Smoke tests

Local Flask, fresh DB:

1. New user signup via founder code → after account create, redirected to `/assessment` (NOT `/welcome`).
2. Try to skip the assessment page → "Skip assessment for now" → lands on `/onboarding` step 1. `User.assessment_complete=True` in DB. No `AssessmentResponse` row.
3. Sign up another user → walk through all 8 pillars, answer all 40 → submit → see results page → click "Begin onboarding" → lands on `/onboarding`. DB: 1 `AssessmentResponse` with valid JSON, `assessment_complete=True`.
4. Submit incomplete data (skip a question on pillar 3) → server validation rejects with 400, returns the pillar slug + question index of the missing answer.
5. Submit invalid Likert value (e.g. 6 or 0) → server validation rejects with 400.
6. Re-take: existing user with `assessment_complete=True` hits `/assessment` → form is fresh (no pre-fill from previous response). Submit → new `AssessmentResponse` row appended (count=2 for that user). Old row preserved.
7. Idempotency: refresh `/assessment/results` while it's the latest → shows the most recent row's scores.
8. Score math sanity: for a pillar with answers `[5,5,5,5,5]`, displayed score is `5.0`. For `[1,1,1,1,1]` → `1.0`. For `[3,3,3,3,3]` → `3.0`. For `[1,2,3,4,5]` → `3.0`.
9. Direct URL hit `/onboarding` while `assessment_complete=False` → does NOT auto-redirect to `/assessment` (assessment is nudged on signup, not enforced indefinitely). User can navigate freely.
10. Stripe-path signup (test with FOUNDER99 in test mode if you have it): after checkout completion → `/subscription/success` → `/assessment`.

---

## Step 6 — Update SoT

- §3 App Scope: add "Member Self-Assessment (8 pillars × 5 Likert)" entry.
- §8 Phase Status: Phase 5 ✅ done with commit SHA.
- §9 Decisions Log: append entry — pillar order locked, question text from memory, schema, redirect helper insertion point, skip semantics.
- §10 Risks: optional — flag that assessment scores are stored as JSON strings (not normalized columns). If we later want to query "members scoring high on Wealth," we'd need to either parse JSON in queries or migrate to normalized rows.

---

## Step 7 — Commit + push

Two commits:

**Commit 1 — schema + lib + routes + redirect helper:**
```
phase-5: assessment models + 40 questions + redirect-after-signup gating

- migration: assessment_response table + user.assessment_complete column
- lib/assessment.py: 8 pillars × 5 verbatim questions from memory
- /assessment, /assessment/submit, /assessment/results, /assessment/skip routes
- _post_signup_redirect helper inserts assessment between checkout/code-signup
  and onboarding when assessment not yet completed
- subscription_success and signup_with_code rewired to use the helper
```
Stage exactly: `models.py`, `migrations/versions/<new>.py`, `lib/assessment.py`, `app.py`.

**Commit 2 — templates + sot:**
```
phase-5: assessment ui (8-pillar wizard + results) + sot
```
Stage exactly: `templates/assessment.html`, `templates/assessment_results.html`, `INTEGRATION-SOURCE-OF-TRUTH.md`.

---

## Step 8 — Report back

5 bullets: schema confirmation, redirect helper hooks, ui flow validated, score math sanity (smoke 8), surprises.

If question text in memory differs from what you'd expect, STOP and report — do NOT rewrite questions. Pillar names are also locked by the parallel landing-page edits memory; if those have shifted, surface to manager before shipping.
