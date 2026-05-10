# Phase 12 — Seed all 8 Spaces with high-density starter content

> Paste into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Goal:** every Space (Sovereign Wealth, Body & Iron, Awake Minds, Brotherhood Ops, The Arsenal, Red Pill Intel, Family & Legacy, Off Grid) has 15–18 substantive starter posts so a new member visiting any Space sees a populated, lived-in feed instead of an empty room.
>
> Off Grid content is **already written verbatim by Kashi** at `seed_content/off_grid_posts.txt` (18 posts, separated by `=====`). The other 7 Spaces get **AI-generated content matching the Off Grid format and brand voice**.

---

## Step 0 — Pull + verify prereqs

```bash
git fetch origin && git status
```
Reset hard if behind: `git reset --hard origin/main`.

**Verify `ANTHROPIC_API_KEY` is set on Railway:**
```bash
railway variables --json | python3 -c "import json,sys; d=json.load(sys.stdin); print('ANTHROPIC_API_KEY:', '<SET>' if d.get('ANTHROPIC_API_KEY') else 'UNSET — STOP, manager has to wire this first')"
```
If unset, STOP and tell the manager. Don't burn API budget on a stub key.

**Verify off_grid_posts.txt is in place:**
```bash
ls -la seed_content/off_grid_posts.txt
grep -c "^=====$" seed_content/off_grid_posts.txt   # expect 17 separators (18 posts)
```

---

## Step 1 — Read first

1. `INTEGRATION-SOURCE-OF-TRUTH.md` §1, §3, §9 — brand identity + Sovereign Code pillars + locked manifesto voice.
2. `templates/landing.html` lines ~575–585 (manifesto) and ~660–670 (FAQ block). Voice anchor.
3. `seed_content/off_grid_posts.txt` — full file. **This is the format/density/voice canon for the other 7 Spaces.** Read all 18 posts. Notice: each post has a clear title (line 1), short opening declaration, structured bullet lists, and a punchy one-liner close. Match this in every generated post.
4. `models.py` `Space` and `Post` models. `Post.content` is plain text — no markdown rendering by default — so embed the title as line 1 of `content` plus blank line, then body. Match Kashi's formatting (bullets as `•`, line breaks preserved).
5. `app.py` `_seed_content()` — see how the 8 canonical Spaces are seeded with `cover_image` paths. You'll query Spaces by name to get their IDs.
6. `phase3_routes.py` and `features_routes.py` — confirm post creation pattern (any extra side effects on `Post` create that we'd miss with a direct ORM insert? check for: notifications, GHL pushes, points awards). For seeding, BYPASS those side effects — direct ORM inserts only. Members shouldn't get notification spam from seed content.

---

## Step 2 — Decisions locked

### 2.1 The 8 Spaces and their content briefs

The Off Grid content is already provided. For the other 7, generate 15 posts each in matching format. Per-Space content brief (use these to direct the AI):

| Space (DB name) | Theme brief for AI | Examples of post titles to seed the AI's variety |
|---|---|---|
| `Sovereign Wealth` | Capital allocation, macro thinking, deal flow, building income streams, real estate, asset protection, taxes. Practical, builder-tone, not financial-advisor cliché. | "How To Think About Cash Flow Before Net Worth", "How To Find Off-Market Deals When You Don't Know Anyone", "How To Start Building a Real Estate Portfolio With Limited Capital" |
| `Body & Iron` | Strength, training discipline, recovery, masculine fitness identity, nutrition without trends, longevity. Operator-tone, not bro-science. | "How To Train Through Decades, Not Months", "How To Build Discipline When Motivation Disappears", "How To Eat Like a Man Who Has Things to Do" |
| `Awake Minds` | Sovereignty thinking, contrarian frameworks, awakening to systemic narratives, reading lists, mental models. Direct, not conspiracy-flavored. | "How To Read in a Way That Actually Changes You", "How To Think Independently in a Connected World", "How To Audit Your Own Beliefs Without Losing Your Footing" |
| `Brotherhood Ops` | Operations of being a man with other men, accountability structures, getting things done together, running a chapter, hosting events. Action-tone. | "How To Run a Monthly Mastermind That Doesn't Die", "How To Bring Hard Truth Without Losing the Friendship", "How To Build a Group That Actually Shows Up" |
| `The Arsenal` | Tools, systems, builders' workshop. Specific tech, hardware, software, gear. Recommendations + warnings. Practical, opinionated. | "How To Set Up a Productivity System You Won't Abandon", "How To Choose Your First EDC Without Overthinking It", "How To Build a Workshop on a Budget" |
| `Red Pill Intel` | Information sovereignty, signal vs noise, media analysis, financial literacy in dystopian times, what's actually happening behind headlines. Direct, calm, not paranoid. | "How To Filter Modern News Without Becoming Cynical", "How To Spot Manufactured Consensus", "How To Read Between the Lines of Government Statistics" |
| `Family & Legacy` | Fatherhood, generations, building for sons, marriage, raising sovereign children. Earnest, not sentimental. | "How To Be a Father Your Sons Want to Become", "How To Build a Family That Outlasts You", "How To Have Hard Conversations With Your Children" |

### 2.2 Format match

Every generated post must match Off Grid's structure exactly:
- **Line 1:** the title, no markdown emphasis (the templates render `Post.content` as plain text)
- **Line 2:** blank
- **Lines 3+:** body. Short paragraphs (1–3 sentences), structured bullet lists where appropriate (using `•` bullet character to match Kashi's style), occasional one-liner closer
- **Length:** 100–300 words, matching Off Grid's range
- **Voice:** declarative, builder-tone, no em-dashes (use periods or commas), no AI-tells, no exclamation points, no hashtags, no emojis
- **Banned phrases** (reject + retry up to 2x if present): `delve into`, `dive in`, `let's explore`, `it's worth noting`, `in today's world`, `at the end of the day`, `unleash`, `journey of`, `embrace`, `harness`, `tapestry`, `realm`, `master the art`

### 2.3 Author attribution + timestamp distribution

Don't attribute all 100+ posts to one user. Distribute across active members so the feed looks organic. **Active member criteria:** `User.has_active_subscription == True`. Excludes inactive accounts.

Distribution algorithm:
1. Pull all active members from prod DB (expect 6–10 currently: Kashi, Bryce, Bram, Rich, plus paid members)
2. Round-robin assign each post across the active member list
3. Stagger `Post.created_at` randomly across the past 21 days. Use `datetime.utcnow() - timedelta(days=random.randint(0, 21), hours=random.randint(0, 23), minutes=random.randint(0, 59))`. Within each Space, posts should NOT cluster on the same day.

### 2.4 Idempotency

Before creating each post, query: `Post.query.filter_by(space_id=<sid>).filter(Post.content.startswith(<title>)).first()`. If a post with that title already exists in that Space, skip. Re-runs of the script don't dupe.

### 2.5 What does NOT happen

- Do NOT trigger notifications, GHL pushes, points awards, or any side effects on Post creation. Bypass those — direct ORM inserts only. (Members shouldn't get 100 notifications when this script runs.)
- Do NOT generate content for Off Grid. That Space's posts come verbatim from the file Kashi wrote.
- Do NOT add poll, image, or special-format posts. Plain `Post.content` only.
- Do NOT change any model schema, route, or template.
- Do NOT commit a one-shot seed script if it has hardcoded content baked in. If you generate content, save it to per-space files in `seed_content/<space_slug>_posts.txt` so it's reviewable + re-runnable.

---

## Step 3 — Implementation

### 3.1 Generation script

Create `scripts/seed_space_content.py`. Three modes:

```bash
# Generate AI content for one space, save to file (does NOT touch DB)
python scripts/seed_space_content.py generate --space "Sovereign Wealth"

# Generate for all 7 non-Off-Grid spaces
python scripts/seed_space_content.py generate --all

# Insert content from per-space text files into DB
python scripts/seed_space_content.py insert --space "Off Grid"
python scripts/seed_space_content.py insert --all
```

The split lets you regenerate AI content (re-running `generate`) without re-inserting, and re-run `insert` idempotently.

Generation uses `lib/auto_post.py` Anthropic client pattern (or directly `import anthropic`). Per-space prompt construction:

```python
PROMPT_TEMPLATE = """You are writing starter posts for the "{space_name}" Space inside Sovereign Society, a private community of operator-class men.

VOICE ANCHOR (the manifesto — match this tone exactly):
{manifesto_block}

CONTENT EXAMPLES (the format/density to match — these are written by the founder for the Off Grid Space):
{three_off_grid_post_examples}

YOUR TASK: write 15 standalone posts for the {space_name} Space.

Theme brief for {space_name}: {theme_brief}

Format rules (match exactly):
- Line 1: title, no markdown emphasis
- Line 2: blank
- Lines 3+: body — short paragraphs, structured bullet lists where appropriate (use • character)
- 100-300 words per post
- Direct, declarative, builder-tone
- NO em-dashes, NO exclamation points, NO hashtags, NO emojis
- BANNED phrases: {banned_phrases}

Output the 15 posts separated by lines containing exactly "=====" (5 equals signs). No preamble, no numbering, no commentary. Just the 15 posts."""
```

Post-validation per generated post:
- Strip any leading/trailing whitespace
- Reject if any banned phrase present (case-insensitive substring match)
- Reject if `—` em-dash present
- Reject if shorter than 80 words OR longer than 400 words
- On rejection: mark for regeneration (retry the whole batch up to 2× or fall back to fewer posts for that space)

### 3.2 Insert script logic

```python
def insert_from_file(space_name, file_path):
    posts_text = open(file_path).read().split("=====")
    space = Space.query.filter_by(name=space_name).first()
    if not space:
        log.error("Space %s not found in DB", space_name)
        return
    
    active_members = User.query.filter_by(has_active_subscription=True).all()
    if not active_members:
        log.error("No active members for attribution")
        return
    
    inserted = 0
    skipped = 0
    for i, raw in enumerate(posts_text):
        body = raw.strip()
        if not body:
            continue
        # Title is the first non-empty line
        title = body.split("\n")[0].strip()
        # Idempotency: skip if a post with this title already exists in this space
        existing = Post.query.filter_by(space_id=space.id).filter(Post.content.startswith(title)).first()
        if existing:
            skipped += 1
            continue
        # Round-robin author across active members
        author = active_members[i % len(active_members)]
        # Stagger created_at: random within past 21 days
        ts = datetime.utcnow() - timedelta(
            days=random.randint(0, 21),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        post = Post(
            user_id=author.id,
            space_id=space.id,
            content=body,
            created_at=ts,
            updated_at=ts,
        )
        db.session.add(post)
        inserted += 1
    db.session.commit()
    log.info("Space %s: inserted %d, skipped (already existed) %d", space_name, inserted, skipped)
```

### 3.3 Run order (manager will execute, not the executor — but document the steps)

```bash
# Step A: generate AI content for the 7 non-Off-Grid spaces
PUBLIC_DB=$(railway variables --service Postgres --json | python3 -c "import json,sys; print(json.load(sys.stdin)['DATABASE_PUBLIC_URL'])")
railway run sh -c "DATABASE_URL='$PUBLIC_DB' .venv/bin/python scripts/seed_space_content.py generate --all"
# Result: 7 new files in seed_content/, one per space

# Step B (manual review): manager session reviews the 7 generated files for
# anything off-brand. If a post is bad, edit the file directly.

# Step C: insert all 8 spaces' content into prod DB
railway run sh -c "DATABASE_URL='$PUBLIC_DB' .venv/bin/python scripts/seed_space_content.py insert --all"
```

### 3.4 Update scripts/README.md

Add a stanza explaining the new `seed_space_content.py` script.

---

## Step 4 — What NOT to break

- The 8 canonical Spaces in prod must keep their `cover_image` paths (Phase 2 fix). Don't touch the Space rows themselves.
- Existing posts in any Space (real member posts) must not be touched, deleted, or modified.
- The 8 placeholder seed users from Phase 0B (if any still exist) — don't attribute new content to them. Filter to `has_active_subscription=True`.
- Don't accidentally trigger checklist auto-checks (Phase 4 wired `_check_item_by_slug` into the post-create handler — bypass that by going directly to ORM, not via `create_post`).
- Don't push to GHL on these inserts.

---

## Step 5 — Smoke tests

Local Flask:

1. `python scripts/seed_space_content.py generate --space "Sovereign Wealth"` — runs, calls Anthropic, writes `seed_content/sovereign_wealth_posts.txt` with 15 posts separated by `=====`.
2. Inspect the file: every post passes the format checks (length, banned phrases, no em-dash).
3. `python scripts/seed_space_content.py insert --space "Sovereign Wealth"` (against local SQLite first) — 15 posts inserted, distributed across local users, timestamps staggered.
4. Re-run step 3: 0 inserted (idempotent), 15 skipped.
5. Visit local `/spaces` → click into Sovereign Wealth → see 15 posts with varied authors + timestamps that look organic (not all today).

Production:

6. Manager runs Step A above against prod via railway run. Reports back to manager with file sizes for each of the 7 generated files.
7. Manager reviews + does any manual edits.
8. Manager runs Step C. Verifies in `/spaces/<id>` for each of the 8 spaces that ~15 posts now appear.

---

## Step 6 — Update SoT

- §3 App Scope: add a note "Spaces seeded with starter content (Phase 12) — Off Grid hand-written by Kashi, others AI-generated against locked brand voice."
- §8 Phase Status: Phase 12 ✅ done with commit SHA.
- §9 Decisions Log: append entry — content generation strategy (Anthropic + manifesto anchor + Off Grid as exemplar), distribution algorithm (round-robin across active members, 21-day timestamp stagger), idempotency on title-prefix match, side-effect bypass.
- §10 Risks: add "AI-generated starter content under member names — disclosure risk if discovered. Mitigation: posts are structurally indistinguishable from member posts; quality bar enforced by banned-phrase + length filters; manager reviewed each space's content before insert."

---

## Step 7 — Commit + push

Two commits:

**Commit 1 — generation + insert script:**
```
phase-12: scripts/seed_space_content.py + per-space content brief table

Generates AI content for 7 spaces matching the Off Grid format Kashi
hand-wrote. Per-space theme briefs lock domain. Banned-phrase + em-dash
filter. Inserts via direct ORM to skip post-create side effects
(no notifications, no GHL pushes, no points awards). Idempotent on
title-prefix match. Round-robin attribution across active members.
21-day created_at stagger.
```
Stage exactly: `scripts/seed_space_content.py`, `scripts/README.md`, `seed_content/off_grid_posts.txt` (if not yet committed).

**Commit 2 — sot:**
```
phase-12: sot — space content seeding strategy locked
```
Stage exactly: `INTEGRATION-SOURCE-OF-TRUTH.md`.

Push.

---

## Step 8 — Report back to manager

5 bullets:

1. **Script shipped** — commit SHA, modes covered (generate single, generate all, insert single, insert all).
2. **Generation smoke test** — for Sovereign Wealth: file size, word counts of first 3 posts, any banned phrases caught + retried.
3. **Insert smoke test** — local results (count inserted, skipped, distribution across users).
4. **Sample output** — paste the FIRST generated post for Sovereign Wealth verbatim into the report so manager can sanity-check voice.
5. **Surprises / blockers** — anything (e.g. `lib/auto_post.py` not yet shipped from Phase 8; Anthropic SDK version mismatch; `Post.created_at` having `default=utcnow` overriding manual ts; an active-member count of <3 making round-robin look odd).

If the first-post sample reads off-brand, STOP and tell manager — don't run for the other 6 spaces. We tune the prompt before burning $10 of API budget.
