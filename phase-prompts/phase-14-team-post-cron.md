# Phase 14 — Sovereign Society Team auto-post queue + every-other-day cron

> Paste into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Goal:** the `Sovereign Society Team` account (user id 11 in prod, email `team@sovereignsociety.rich`) posts new content to each Space at an every-other-day cadence, drawing from a queue that Kashi/manager can append to anytime.

---

## Step 0 — Pull

```bash
git fetch origin && git status
```
Reset hard if behind.

---

## Step 1 — Read first

1. `INTEGRATION-SOURCE-OF-TRUTH.md` §9 — Phase 12 + the manager-session 2026-05-09→11 entries that created the Team user and bulk-seeded backdated content.
2. `cron.py` — existing CLI command pattern (`cli_digest`, `cli_test_email`, `cli_daily_auto_post` if shipped). New command follows the same shape.
3. `models.py` — `Post`, `Space`, `User`. You're adding ONE new model.
4. `scripts/seed_space_content.py` — pattern for `--space` filter, idempotency, error handling. New enqueue script borrows the style.
5. `OPERATIONS.md` — Railway cron section. You'll add an entry.

---

## Step 2 — Decisions locked

### 2.1 New model `TeamPostQueue`

Holds the queue of pending Team posts per Space. One row per future post.

```python
class TeamPostQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    space_id = db.Column(db.Integer, db.ForeignKey("space.id"), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    queue_position = db.Column(db.Integer, nullable=False, default=0)  # ordering hint within a space
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)  # 'pending' | 'published' | 'skipped'
    published_post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    published_at = db.Column(db.DateTime, nullable=True)

    space = db.relationship("Space")
    published_post = db.relationship("Post", foreign_keys=[published_post_id])
```

`@validates("status")` rejects values outside the locked set.

### 2.2 Cadence rule

**Every other day per space.** If a Space's most recent Team post is < `TEAM_POST_CADENCE_DAYS` days old (default 2), the cron skips that Space this run. If ≥ cadence AND queue has pending content, publish the next item.

Cadence is configurable via env var `TEAM_POST_CADENCE_DAYS` so Kashi can tune later without code change.

Note: this measures from the LAST TEAM POST regardless of how it got there (backdated, manual via /admin, prior cron run). So the existing 123 backdated posts (Phase 12 reseed) automatically respect cadence — the cron won't double-fire if a recent backdated post is < 2 days old.

### 2.3 What the cron does NOT do

- Does NOT publish multiple posts to the same Space in one run. One Space, one post per cron run (only if cadence is met).
- Does NOT skip ahead to a "next priority" item. Strict FIFO by `(queue_position ASC, created_at ASC)`.
- Does NOT trigger notifications / GHL pushes / engagement-tagging. Push notifications are a Phase 7 (iOS shell) concern; team posts shouldn't be in the engagement-tagging path.
- Does NOT auto-populate the queue from `seed_content/*.txt` files. That work is for the manager session (one-off ingest commands) — separate from the daily cron.
- Does NOT delete published rows from `team_post_queue` — preserves audit trail. Rows just transition `pending` → `published` with `published_at` set.

### 2.4 Enqueue script

`scripts/team_post_enqueue.py` accepts content via stdin or file:

```bash
# From stdin:
echo "Post body here..." | python scripts/team_post_enqueue.py --space "Sovereign Wealth"

# From file:
python scripts/team_post_enqueue.py --space "Body & Iron" --file path/to/post.txt

# Bulk from an existing seed_content file (one post per ===== separator):
python scripts/team_post_enqueue.py --space "Off Grid" --bulk-file seed_content/off_grid_posts.txt
```

The bulk-file mode lets manager session quickly enqueue chunks of pre-written content.

### 2.5 Cron schedule

Daily at 13:00 UTC (9 AM ET / 8 AM ET DST). Manager will set up the Railway cron job in dashboard after this phase ships.

Cron expression: `0 13 * * *`. Command: `flask cron team-post-publish`.

Within the cron command, the every-other-day check ensures no Space gets a post twice per cadence even if the cron itself runs daily.

### 2.6 Status & visibility

`/admin` page (or a new `/admin/team-queue` sub-page) shows:
- Pending count per Space
- Last published timestamp per Space
- A "skip next" button per Space (sets the next pending row to `skipped` without publishing)

Admin tooling can be minimal — a single new template + route is enough. Manager session may want this for quick visibility into queue state.

---

## Step 3 — Implementation

### 3.1 Schema migration

Generate via `flask db migrate -m "team_post_queue: scheduled team posts"`.

Standard alembic. Add the table + indexes per § 2.1. **Use `server_default=sa.text("'pending'")` for the status default and `sa.false()` if you need any boolean defaults** (postgres-vs-sqlite compat — same gotcha that took prod down 2026-05-03 and again 2026-05-04).

### 3.2 `cron.py` new command

```python
@cron_cli.command("team-post-publish")
def cli_team_post_publish():
    """Publish next-in-queue Team posts for each Space whose cadence is up.

    Cadence: TEAM_POST_CADENCE_DAYS env var (default 2). A Space gets a new
    post only if its most recent Team post is older than that.
    """
    from datetime import datetime, timedelta
    from models import db, User, Space, Post, TeamPostQueue

    team = User.query.filter_by(email="team@sovereignsociety.rich").first()
    if not team:
        click.echo("[TEAM-POST] Team user not found. Aborting.")
        return

    cadence = int(os.environ.get("TEAM_POST_CADENCE_DAYS", "2"))
    cadence_delta = timedelta(days=cadence)
    now = datetime.utcnow()
    threshold = now - cadence_delta

    published = 0
    skipped_too_recent = 0
    skipped_empty_queue = 0

    for space in Space.query.order_by(Space.id).all():
        last = Post.query.filter_by(user_id=team.id, space_id=space.id).order_by(Post.created_at.desc()).first()
        if last and last.created_at > threshold:
            skipped_too_recent += 1
            continue

        next_q = TeamPostQueue.query.filter_by(space_id=space.id, status="pending").order_by(
            TeamPostQueue.queue_position.asc(), TeamPostQueue.created_at.asc()
        ).first()
        if not next_q:
            skipped_empty_queue += 1
            continue

        p = Post(user_id=team.id, space_id=space.id, content=next_q.content, created_at=now, updated_at=now)
        db.session.add(p)
        db.session.flush()  # get p.id
        next_q.status = "published"
        next_q.published_post_id = p.id
        next_q.published_at = now
        published += 1
        click.echo(f"[TEAM-POST] published in {space.name!r}: {next_q.content[:70]!r}")

    db.session.commit()
    click.echo(f"[TEAM-POST] cadence={cadence}d  published={published}  skipped_recent={skipped_too_recent}  skipped_empty={skipped_empty_queue}")
```

### 3.3 Enqueue CLI

`scripts/team_post_enqueue.py`:

```python
#!/usr/bin/env python3
"""Append a Team post to the cron queue.

Single-post (stdin or --file):
    echo "Body" | python scripts/team_post_enqueue.py --space "Sovereign Wealth"
    python scripts/team_post_enqueue.py --space "Body & Iron" --file post.txt

Bulk (one post per '=====' line):
    python scripts/team_post_enqueue.py --space "Off Grid" --bulk-file seed_content/off_grid_posts.txt

Bulk skips chunks that start with '#' header comments (matches the
seed_content file format from Phase 12).
"""
import sys, os, argparse, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app
from models import db, Space, TeamPostQueue

SEP = re.compile(r"^\s*=====\s*$", re.MULTILINE)

def _clean(raw):
    lines = [l for l in raw.split("\n") if not l.lstrip().startswith("#")]
    return "\n".join(lines).strip()

def enqueue_one(space_name, content):
    space = Space.query.filter_by(name=space_name).first()
    if not space:
        raise SystemExit(f"No Space named {space_name!r}")
    max_pos = db.session.query(db.func.max(TeamPostQueue.queue_position)).filter_by(space_id=space.id).scalar() or 0
    q = TeamPostQueue(space_id=space.id, content=content, queue_position=max_pos + 1)
    db.session.add(q)
    db.session.flush()
    return q

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--space", required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--file")
    g.add_argument("--bulk-file")
    args = p.parse_args()

    with app.app_context():
        if args.bulk_file:
            text = open(args.bulk_file).read()
            posts = [_clean(c) for c in SEP.split(text)]
            posts = [p for p in posts if p]
            for body in posts:
                q = enqueue_one(args.space, body)
                print(f"  +{q.id} pos={q.queue_position}: {body[:60]!r}")
            print(f"Enqueued {len(posts)} posts to {args.space}.")
        else:
            if args.file:
                body = _clean(open(args.file).read())
            else:
                body = _clean(sys.stdin.read())
            if not body:
                raise SystemExit("Empty body.")
            q = enqueue_one(args.space, body)
            print(f"Enqueued #{q.id} (pos={q.queue_position}) to {args.space}: {body[:70]!r}")
        db.session.commit()

if __name__ == "__main__":
    main()
```

### 3.4 Admin queue view

Add `/admin/team-queue` route + template `templates/admin_team_queue.html`. Minimal:

- Per-space block: name, pending count, last-published-at, "skip next" button (POST to `/admin/team-queue/skip/<space_id>` — sets next pending row to `skipped`).
- Don't add edit/delete UI yet. Manager session handles those via `flask shell` if needed.

Admin-gated via `@admin_required`.

### 3.5 `scripts/README.md` entry

Add a stanza explaining `team_post_enqueue.py` — same shape as the existing entries.

### 3.6 `OPERATIONS.md` cron stanza

Add at the bottom:

```
### Schedule team-post-publish in Railway
1. Railway → New Cron Job
2. Schedule: `0 13 * * *` (daily at 13:00 UTC = 9 AM ET / 8 AM EDT)
3. Command: `flask cron team-post-publish`

Cadence: TEAM_POST_CADENCE_DAYS env var (default 2). To change to weekly, set 7.
```

### 3.7 Env var (manager will set on Railway after phase lands)

`TEAM_POST_CADENCE_DAYS=2` (default — every other day). Optional override.

---

## Step 4 — What NOT to do

- Do NOT migrate the existing seed_content/*.txt content into `team_post_queue` rows. The 123 already-published posts stay in the `post` table; the queue is only for future content.
- Do NOT add a "draft / review" workflow. Posts go straight from queue → published when cadence is up. If Kashi wants review later, that's a separate phase.
- Do NOT add cross-Space deduplication (preventing the same content from appearing in two Spaces). Manager handles that at enqueue time.
- Do NOT change the existing `Post` model schema.
- Do NOT alter the existing `Team` user or any other User row.
- Do NOT touch GHL, Stripe, R2, or any unrelated subsystem.

---

## Step 5 — Smoke tests

Local Flask:

1. Migration applies clean. `TeamPostQueue` table exists.
2. Validates: `TeamPostQueue(status="bogus")` raises ValueError.
3. Enqueue one post via stdin: `echo "Test post body" | python scripts/team_post_enqueue.py --space "Sovereign Wealth"` → prints enqueued id, position. DB has the row pending.
4. Enqueue bulk: `python scripts/team_post_enqueue.py --space "Off Grid" --bulk-file seed_content/off_grid_posts.txt` → all 18 enqueued. (Won't re-publish since those are already in `post` table as backdated.)
5. Cron with cadence not yet up: `flask cron team-post-publish` with TEAM_POST_CADENCE_DAYS=2 and a Team post from today already in every Space → output `skipped_recent=8 skipped_empty=0 published=0`.
6. Cron with cadence up: temporarily set a Space's most recent Team post `created_at` to 5 days ago. Run cron. That Space's first pending queue row publishes; new Post appears; queue row flips to `status='published'` with `published_post_id` and `published_at` set. Other Spaces unchanged.
7. Re-run cron immediately after step 6: that Space now has a fresh team post (created today), so it skips. `published=0`.
8. Admin queue view: hit `/admin/team-queue` as admin → see per-space counts + last-published. Non-admin → 403.
9. Negative: queue is empty for a Space whose cadence is up → cron prints `skipped_empty=1`, no error.
10. Idempotency: run cron 3 times in a row. Net effect on DB is the same as running it once (since cadence prevents re-fire within the window).

Production verification (manager handles after deploy):

11. After phase lands + manager sets Railway cron, manager runs one manual `railway run flask cron team-post-publish` to verify it executes cleanly and reports zero published (since all current Spaces have a fresh Team post from the Phase 12 reseed).
12. Manager enqueues 2-3 test posts to one Space. Verifies they're pending. Waits for next day's cron to publish naturally (or runs manually with cadence override).

---

## Step 6 — Update SoT

- §3 App Scope: add line under Activity Feed: "Team auto-post queue + every-other-day cron (Phase 14)."
- §5 Env Vars: add `TEAM_POST_CADENCE_DAYS` (default 2, optional).
- §8 Phase Status: Phase 14 ✅ done with commit SHA.
- §9 Decisions Log: append entry — cadence design, queue/publish separation, status vocab, idempotency model.
- §10 Risks: 
  - "If TEAM_POST_CADENCE_DAYS is changed mid-deploy, the cadence check uses the NEW value — so a shortened cadence (e.g. 2→1) can trigger publishes for Spaces whose last post was yesterday. Acceptable. A lengthened cadence (2→7) makes the queue go quiet until enough time elapses."
  - "Cron failures are silent unless Railway alerting is set up. Manager should check Railway logs weekly to confirm cron is firing."

---

## Step 7 — Commit + push

Three commits:

**Commit 1 — schema + model validation:**
```
phase-14: team_post_queue model + migration

New table for the Sovereign Society Team post queue. Status vocab locked
(pending|published|skipped). FK to space and post (nullable, populated on
publish). Indexes on space_id + status for cron lookup.
```
Stage exactly: `models.py`, `migrations/versions/<new>.py`.

**Commit 2 — cron + enqueue script + admin view:**
```
phase-14: team-post-publish cron + enqueue cli + admin queue view

Cron runs daily, per-space cadence (TEAM_POST_CADENCE_DAYS, default 2).
Enqueue script supports single (stdin/file) or bulk (===== separator)
content ingest. Admin /admin/team-queue page surfaces queue state.
```
Stage exactly: `cron.py`, `app.py` (admin route + template wiring), `scripts/team_post_enqueue.py`, `templates/admin_team_queue.html`.

**Commit 3 — docs + sot:**
```
phase-14: ops doc + sot — team-post cron at 13 UTC
```
Stage exactly: `OPERATIONS.md`, `scripts/README.md`, `INTEGRATION-SOURCE-OF-TRUTH.md`.

Push.

---

## Step 8 — Report back to manager

7 bullets:

1. Schema applied (revid + indexes).
2. Cron command output for the no-op smoke test (step 5/11): paste verbatim.
3. Enqueue single-post smoke result + DB row contents.
4. Enqueue bulk-file smoke result (count).
5. Cron-with-cadence-up smoke (step 6): paste output + the new Post id created.
6. Admin queue view URL works for admin, 403 for non-admin.
7. Surprises / blockers — anything (e.g. Flask-SQLAlchemy 3.x relationship cascade quirk on TeamPostQueue ↔ Post; an existing /admin route collision; the team user not yet at id 11 in dev DB; etc.).

If anything is genuinely ambiguous, STOP and report — don't decide.
