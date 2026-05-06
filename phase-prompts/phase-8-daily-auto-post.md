# Phase 8 — Daily auto-post on Kashi's account

> Paste into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Goal:** every day at a scheduled time, an AI-generated post appears in the SS feed under Kashi's user account. Members see a fresh post daily without Kashi having to manually create it.
>
> ⚠️ Manager assumption: "automatic posts on my account" means the in-app `/feed`, posted under the User row tied to `kashi@thebreathcoachschool.com`. NOT external platforms (X / Instagram). If the executor reads this and that assumption is wrong, STOP and tell the manager.

---

## Step 0 — Pull

```bash
git fetch origin && git status
```
Reset hard if behind. `git reset --hard origin/main`.

---

## Step 1 — Read first

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — full file, especially §9 Decisions Log (8 Sovereign Code pillars from Phase 5, brand voice locked from landing).
2. `cron.py` — existing CLI command pattern (`cli_digest`, `cli_test_email`). Your new `cli_daily_auto_post` follows the same shape.
3. `features_routes.py` — the `/wingman` handler. Existing Anthropic call pattern with API key check + graceful degrade. Mirror the same approach.
4. `models.py` — `Post` model. You'll add ONE column.
5. `lib/assessment.py` — see how the 8 pillars are structured. Use the same pillar list as the topic-rotation anchor.
6. `OPERATIONS.md` — Railway Cron section. You'll add a new cron entry.
7. Memory file `~/.claude/projects/-Users-kenneth-anti-billionaires-app/memory/project_pending_landing_edits.md` — the 8-line "Sovereign Code" body copy. This is the canonical voice anchor.

---

## Step 2 — Decisions locked

### 2.1 AI provider

Anthropic (already wired for `/wingman`). Use the existing `anthropic` Python SDK and `ANTHROPIC_API_KEY` env var. Default model: read from `ANTHROPIC_MODEL` env (already set to `claude-sonnet-4-6` per earlier manager work).

If `ANTHROPIC_API_KEY` is unset/placeholder, the cron command should log a clear warning and exit cleanly without creating a post. Same graceful-degrade pattern as `/wingman`.

### 2.2 Topic rotation

The 8 Sovereign Code pillars (locked in Phase 5):
`Purpose, Strength, Wealth, Brotherhood, Family, Faith, Awareness, Control`

Each pillar has multiple angles. Build a rotation table of 32 daily themes (4 per pillar × 8 pillars = ~5-week cycle before repeats). Examples per pillar:

- Purpose: clarity check / 5-year vision / morning ritual / mission alignment
- Strength: training discipline / mental resilience / discomfort reps / physical standard
- Wealth: capital allocation / income streams / financial independence math / skill investment
- Brotherhood: accountability / showing up / hard truths / building circles
- Family: presence / legacy / providing / honest communication
- Faith: higher power / grounding / spiritual practice / trust over fear
- Awareness: red-pill moment / blind spots / mainstream noise / conscious work
- Control: time discipline / emotional management / self-commitments / mental health

Build the rotation table in `lib/auto_post.py`. Pick the day's theme deterministically by `date.today().toordinal() % 32`.

### 2.3 Voice + format

- 80–250 words per post
- No em-dashes (—), per the brand-voice scrub from earlier this week
- No AI tells: ban the phrases `delve into`, `dive in`, `let's explore`, `it's worth noting`, `in today's world`, `at the end of the day`, `unleash your potential`, `journey of`, `remember`, `embrace`. Validate post-generation; reject + retry up to 3 times if any banned phrase appears.
- Open with a concrete observation, story fragment, or hard question. NOT a generic statement.
- Manifesto voice: direct, masculine, builder-tone. Quote the locked landing copy as voice anchor.
- End with a question or a call that invites reply (engagement driver).
- No hashtags, no emoji, no exclamation points.

### 2.4 User attribution

The post is attributed to the User whose email matches the FIRST entry in `ADMIN_EMAILS` env var (currently `kashi@thebreathcoachschool.com`). If that user doesn't exist or the env var is unset, log a clear error and exit.

### 2.5 Idempotency

Add `Post.auto_generated = db.Column(db.Boolean, nullable=False, default=False, index=True)`.

Before generating, query: any Post row with `user_id == kashi_user.id AND auto_generated == True AND date(created_at) == today`. If yes, skip — don't re-post.

This makes the cron command safe to run multiple times per day (e.g. on Railway redeploys, or accidental double-fires).

### 2.6 Schedule

Default schedule: **9:00 AM Eastern Time daily**. UTC equivalent depends on DST:
- EST (Nov–Mar): 14:00 UTC
- EDT (Mar–Nov): 13:00 UTC

Documented in `OPERATIONS.md`. Railway Cron does not support timezone-aware schedules — pick UTC. **Use 14:00 UTC year-round**; Kashi can adjust via Railway dashboard if EDT shift matters.

Cron expression: `0 14 * * *` (every day at 14:00 UTC).

### 2.7 What does NOT happen here

- Do NOT post to external platforms (X, Instagram, LinkedIn). In-app SS feed only.
- Do NOT generate images. Text post only.
- Do NOT add admin-approval queue. Auto-posts go straight to the feed (Kashi can delete via existing admin tools).
- Do NOT touch the Wingman feature, leveling system, points, or notifications.
- Do NOT add post scheduling for any other user account. Kashi's account only.
- Do NOT create a UI for editing the topic rotation. The 32 themes are hardcoded in `lib/auto_post.py`; Kashi/manager edits in code if rotation needs to change.

---

## Step 3 — Implementation

### 3.1 Schema migration

Add `auto_generated` column to `Post`:
```python
auto_generated = db.Column(db.Boolean, nullable=False, default=False, index=True)
```

Generate migration: `flask db migrate -m "post: add auto_generated flag"`. Verify the auto-detection caught the column + index. **Use `server_default=sa.false()` for the default** (postgres-compatible — same gotcha as the Phase 3 migration that took prod down on 2026-05-03).

### 3.2 `lib/auto_post.py`

```python
"""Daily auto-post generator. Uses Anthropic to write a single feed post in
Kashi's voice across a 32-theme rotation anchored to the 8 Sovereign Code
pillars.

Env vars consumed:
    ANTHROPIC_API_KEY   — required; client no-ops if unset
    ANTHROPIC_MODEL     — defaults to claude-sonnet-4-6
    ADMIN_EMAILS        — first entry is the posting user's email
"""
import os
from datetime import date

PILLARS_AND_ANGLES = [
    ("Purpose",     "clarity check"),
    ("Purpose",     "5-year vision"),
    ("Purpose",     "morning ritual"),
    ("Purpose",     "mission alignment"),
    ("Strength",    "training discipline"),
    # ... full 32 entries; one per (pillar, angle) ...
]

BANNED_PHRASES = [
    "delve into", "dive in", "let's explore", "it's worth noting",
    "in today's world", "at the end of the day", "unleash your potential",
    "journey of", "remember", "embrace",
]

VOICE_ANCHOR = """[paste the manifesto block from landing.html lines ~575-585 here verbatim]"""

def theme_for_today():
    return PILLARS_AND_ANGLES[date.today().toordinal() % len(PILLARS_AND_ANGLES)]

def _build_prompt(pillar, angle):
    return f"""You write daily posts for the Sovereign Society community feed in the voice of Kashi, the founder.

Voice anchor (the manifesto — match this tone):
{VOICE_ANCHOR}

Today's pillar: {pillar}
Today's angle: {angle}

Rules:
- 80 to 250 words.
- Open with a concrete observation, story fragment, or hard question. NOT a generic statement.
- Direct, masculine, builder-tone. No motivational-speaker fluff.
- End with a question or call that invites reply.
- NO em-dashes. NO hashtags, emoji, or exclamation points.
- Avoid these phrases: {", ".join(BANNED_PHRASES)}.
- Do not name the pillar or angle in the post itself.

Output the post text only. No preamble, no quotes around it, no metadata."""

def generate_post_text() -> str | None:
    """Returns post text, or None if AI is unavailable / fails after retries."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or "REPLACE" in api_key or "placeholder" in api_key.lower():
        return None
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    pillar, angle = theme_for_today()
    prompt = _build_prompt(pillar, angle)
    for attempt in range(3):
        msg = client.messages.create(
            model=model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if any(p.lower() in text.lower() for p in BANNED_PHRASES):
            continue
        if "—" in text:
            continue
        return text
    return None
```

### 3.3 `cron.py` new command

```python
@cron_cli.command("daily-auto-post")
def cli_daily_auto_post():
    """Generate a single AI-authored post for today and attribute to the
    first ADMIN_EMAILS user. Idempotent: skips if today's auto post already exists."""
    from datetime import datetime, date
    from models import db, User, Post
    from lib.auto_post import generate_post_text

    admin_emails = [e.strip() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]
    if not admin_emails:
        click.echo("[AUTOPOST] ADMIN_EMAILS unset; cannot determine posting user. Exiting.")
        return
    posting_user = User.query.filter_by(email=admin_emails[0].lower()).first()
    if not posting_user:
        click.echo(f"[AUTOPOST] No user found for {admin_emails[0]}. Exiting.")
        return

    today = date.today()
    existing = Post.query.filter(
        Post.user_id == posting_user.id,
        Post.auto_generated == True,
        db.func.date(Post.created_at) == today,
    ).first()
    if existing:
        click.echo(f"[AUTOPOST] Today's auto post already exists (id {existing.id}). Skipping.")
        return

    text = generate_post_text()
    if not text:
        click.echo("[AUTOPOST] generate_post_text returned None (AI unavailable or repeated banned-phrase rejection). Exiting.")
        return

    p = Post(user_id=posting_user.id, content=text, auto_generated=True)
    db.session.add(p)
    db.session.commit()
    click.echo(f"[AUTOPOST] Created post {p.id} ({len(text)} chars) under user {posting_user.id}")
```

### 3.4 Railway cron entry

Document in `OPERATIONS.md` under "Schedule weekly digest in Railway":

```
### Schedule daily auto-post in Railway
1. Railway → New Cron Job
2. Schedule: `0 14 * * *` (every day at 14:00 UTC = 9 AM EST / 10 AM EDT)
3. Command: `flask cron daily-auto-post`
```

Manager session will run this in the dashboard after the phase ships. Don't try to wire it via CLI from inside this phase.

### 3.5 Admin override

Add a small `/admin/auto-post-now` POST route that runs the same logic as the cron command but synchronously, for manual testing. Admin-only via `@admin_required`. Returns JSON `{"posted": True, "post_id": N}` or `{"posted": False, "reason": "..."}`. Useful for Kashi to test the flow without waiting for 14:00 UTC.

---

## Step 4 — What NOT to do

- Do NOT call any AI provider other than Anthropic.
- Do NOT cache prompts — each call is fresh.
- Do NOT log post text to stdout in production (it'll show in Railway logs and skew clipboard reads).
- Do NOT touch the existing `/wingman` route.
- Do NOT add a UI to view auto-posted-vs-human-posted on the feed (auto_generated is internal metadata).
- Do NOT modify other users' content.

---

## Step 5 — Smoke tests

Local Flask:

1. Migration applies clean. `Post.auto_generated` column exists with default False, index present. Verify via `flask shell`: `Post.query.filter_by(auto_generated=True).count()` returns 0.
2. With `ANTHROPIC_API_KEY` unset → `flask cron daily-auto-post` exits with the AI-unavailable message, no Post created.
3. With `ANTHROPIC_API_KEY` set to a valid test key + `ADMIN_EMAILS` set → first run creates a Post. Second run (same day) is a no-op (idempotency).
4. The created Post is visible at `/feed` (logged in) under Kashi's name.
5. Banned-phrase test: monkeypatch `generate_post_text` to return a string containing "delve into" once then a clean string. Verify the retry loop handles it (post created from the second attempt).
6. Em-dash filter: same monkeypatch test for "—".
7. `/admin/auto-post-now` POST as admin → returns `{"posted": True, ...}`. Same idempotency guard applies (second hit same day = `{"posted": False, "reason": "already posted today"}`).
8. Non-admin user POSTing `/admin/auto-post-now` → 403.

Production verification (after deploy):

9. After commit lands and Railway redeploys, log into `/admin` as Kashi, hit the auto-post-now button (or POST the route directly with a CSRF token). Verify a new post appears on `/feed`. Read it — confirm voice + length + no banned phrases + no em-dashes.
10. Set the Railway Cron job (manager will do this in dashboard, not your job).

---

## Step 6 — Update SoT

- §3 App Scope: add an entry under "Activity Feed" or as its own line: "Daily auto-post (Anthropic-generated, Kashi's account, 32-theme rotation)."
- §5 Env Vars: add note under `ANTHROPIC_API_KEY` and `ADMIN_EMAILS` that both are now load-bearing for the daily auto-post.
- §8 Phase Status: add Phase 8 ✅ done with commit SHA.
- §9 Decisions Log: append entry — voice rules, banned phrases, 32-theme rotation, idempotency model, time slot.
- §10 Risks: 
  - Cost — Anthropic API charges per call. ~365 calls/year × ~600 tokens × $0.003/1K ≈ $0.66/year. Negligible.
  - Quality — AI may produce off-brand content. Banned-phrase filter + em-dash filter help. Kashi can delete any bad post via existing admin tools.
  - Outage — if Anthropic is down on a given day, no post for that day. Acceptable degradation.
  - Bryce account — if Bryce ever becomes the first ADMIN_EMAILS entry, the post would attribute to him instead of Kashi. Manager-known footgun; document in operational notes.

---

## Step 7 — Commit + push

Three commits:

**Commit 1 — schema:**
```
phase-8: post.auto_generated column + migration
```
Stage exactly: `models.py`, `migrations/versions/<new>.py`.

**Commit 2 — lib + cron command + admin override:**
```
phase-8: daily auto-post — anthropic-generated, 32-theme rotation, idempotent

- lib/auto_post.py: pillar×angle rotation, banned-phrase + em-dash filter,
  graceful degrade if anthropic key unset
- cron.py: cli_daily_auto_post command, idempotency on (user, date, auto_generated)
- /admin/auto-post-now route for manual triggering
```
Stage exactly: `lib/auto_post.py`, `cron.py`, `app.py`.

**Commit 3 — ops + sot:**
```
phase-8: ops doc + sot — daily auto-post scheduled at 14 UTC
```
Stage exactly: `OPERATIONS.md`, `INTEGRATION-SOURCE-OF-TRUTH.md`.

---

## Step 8 — Report back

5 bullets:

1. Schema applied (revid + index).
2. Library + cron + admin route shipped (commit SHA).
3. Smoke tests 1-8 results.
4. Live verification: `/admin/auto-post-now` produced a real post on prod feed; quote the first sentence of the generated post in the report so the manager can sanity-check voice.
5. Surprises / blockers — anything (e.g. `anthropic` SDK version mismatch, `claude-sonnet-4-6` model id rejected, cron registration shape changed, Kashi user not found by ADMIN_EMAILS lookup).

If anything looks off — STOP and report. Especially flag if the generated text has voice issues the banned-phrase filter doesn't catch (executor reads the first prod post; if it sounds AI-slop, escalate to manager so we can tune the prompt before scheduling daily).
