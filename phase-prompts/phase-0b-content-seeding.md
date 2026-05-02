# Phase 0B — Seed the Empty Community with Placeholder Content + Imagery

> Paste this entire prompt into a fresh Claude Code session opened in the local repo. Do not modify the prompt — the manager session sized scope deliberately. This phase MUST come after Phase 0A is committed (verify by running `git log --oneline -5` and confirming you see `phase-0a:` in the recent log).

---

## Step 0 — Pull before reading

```bash
git fetch origin && git status
```

If `main` is behind origin: `git reset --hard origin/main` (after confirming no uncommitted local work). The repo lives in iCloud Drive on at least one machine, which causes ref drift; never trust `git pull` alone.

---

## Step 1 — Read first (mandatory)

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — the full file. Pay attention to §9 Decisions Log entries from 2026-05-02 (business model, trial, ICP, day-1 features, brand voice).
2. `templates/landing.html` — the canonical brand voice (manifesto + 6 pillars + tier names). Match this voice exactly in placeholder copy.
3. `models.py` — full file. Note the field shapes for User, Post, Space, Win, Deal, Resource, WeeklyChallenge, Event, etc. You'll be inserting into these tables.
4. `app.py` — find the `_seed_content()` function. It already seeds 6 Spaces, 7 default Badges, and a few recurring Events. **Do NOT modify `_seed_content()`.** Your work goes in a NEW seed function in a NEW file.
5. `populate_content.py` — the standalone wrapper. You'll add a sibling wrapper for placeholder content (`seed_placeholders.py`).
6. Memory: read `~/.claude/projects/-Users-kashikeefe-Library-Mobile-Documents-com-apple-CloudDocs-Desktop-anti-billionaires-app/memory/feedback_copy_no_sobriety_framing.md` if present — applies to all placeholder copy in this phase.

---

## Step 2 — Locked context (DO NOT change)

- **ICP:** sovereign-pilled men, age 30–50, income $100k–$500k, US-primary. Disillusionment-driven (food/money/media skeptics), with empty-circle pain as secondary.
- **Voice:** masculine, bold, declarative. No softening. Match landing.html manifesto cadence ("food is poisoned, money is fake," "build the fire," "operators, builders, protectors"). Serif for emotional copy, mono for HUD/labels.
- **No sobriety/consumption framing.** Do not write any placeholder content where "drinking," "alcohol," "sobriety," or consumption habits appear as a metaphor or pain hook. Voice is about who men are around, not what they consume.
- **Color palette:** gold #D4AF37 on black #0A0A0A. Every generated image must respect this.
- **Aesthetic:** abstract, geometric, line-art, minimal. **NO photorealistic people in any generated image** (uncanny-valley AI faces will kill the brand for this ICP). Symbols, architecture, geometry, light only.

---

## Step 3 — Goal

The community ships with 6 seeded Spaces but **0 posts, 0 wins, 0 deals, 0 resources, 0 challenges, 0 reels, 0 stories**. A real member who signs up and lands on the feed sees an empty room → instant churn.

Seed enough placeholder content + imagery that the community **looks alive on first login**, while staying:
- Honest (placeholder accounts clearly labeled in their bio as pre-launch seed)
- Cleanable (one DB query removes all placeholder users + their cascaded content)
- On-brand (every word + image passes the manifesto smell test)

---

## Step 4 — What to create

### 4.1 — New file: `seed_placeholders.py`

Single, idempotent script. Run with `python seed_placeholders.py`. It must:

1. Create **8 placeholder users** with email pattern `seed.<slug>@sovereign.placeholder` so they can be deleted with one query later. Each user has:
   - Realistic name (first + last initial format), e.g., "Marcus W.", "James R."
   - Bio ending with this exact suffix on its own line: `— Founding Voice (pre-launch seed account)`
   - City, country, lat, lng (real US coordinates, geographically distributed: TX, NY, FL, ID, TN, WY, MT, NC)
   - `points` value between 200 and 4500 (mix of tiers/levels)
   - `streak_days` between 3 and 45
   - `email_verified=True`, `subscription_status="active"` (so they appear as real members)
   - `referral_code` populated
   - Profile photo: monogram SVG (initials in gold on black, see 4.2)
   - `created_at` backdated 30–90 days
   - `is_admin=False`

2. Create **2–3 posts per Space** (12–18 total) attributed to the placeholder users. Posts must:
   - Match the manifesto voice (declarative, masculine, sovereign-pilled)
   - Be 80–250 words each
   - Vary in topic appropriate to each Space (Vault = deal mechanics; Business Strategy = scaling/operating; Networking = intros/connections; Investment = macro/markets; Wellness = strength/protocols; Creator's Corner = building/IP)
   - **No sobriety/consumption framing** (see locked rule above)
   - Backdated `created_at` between 60 days ago and 2 days ago, randomized
   - 30% should have `image_path` pointing to a generated cover (see 4.2)

3. Create **3–4 Wins** on the Wins Wall:
   - Real-sounding outcomes (closed a deal, hit a milestone, completed a challenge)
   - 60–150 words description
   - Each gets a generated cover image (see 4.2)
   - Distributed across users
   - Backdated 7–45 days

4. Create **3–4 Deals** on the Deal Board:
   - Mix of categories (`investment`, `partnership`, `service`, `hiring`)
   - Realistic but generic enough to be obvious placeholders to a careful reader
   - 100–200 words description
   - Each gets a generated cover image
   - Backdated 5–20 days

5. Create **6–8 Resources** in the Resource Vault, mix of categories (book, tool, course, podcast, article, template):
   - Real items (existing books / tools / podcasts) curated to match the ICP — e.g., "The Sovereign Individual" (Davidson/Rees-Mogg), "Antifragile" (Taleb), "Unscripted" (DeMarco), "The Daily Stoic" (Holiday)
   - 30–80 word description per resource
   - 2–4 of them get an upvote from each placeholder user (so they show non-zero engagement)
   - No generated images required (resources don't have a cover field unless one already exists — verify with models.py)

6. Create **1 active Weekly Challenge:**
   - 7-day challenge starting today, ending in 7 days
   - Title: something physical or operational, on-brand (e.g., "7-Day Cold Plunge Discipline" or "30 Calls in 7 Days")
   - 200-word description
   - 2–3 placeholder submissions from placeholder users

7. Create **3 upcoming Events:**
   - "Mastermind Call" — recurring, dated 7 days from today
   - "Networking Mixer" — dated 14 days from today
   - "Guest Speaker — [Name]" — dated 21 days from today, plausible real-sounding speaker name (NOT an actual public figure — make one up)
   - Each gets a generated cover image
   - 3–5 placeholder users RSVPed `going` to each

8. Optional (skip if time-constrained): 2–3 Stories from 1–2 placeholder users, set to expire in 24 hrs.

### 4.2 — Image generation via Nano Banana

Use the `nano-banana-2-skill` Skill. Generate the following images. **All images must use the same visual language**: abstract, geometric, line-art OR low-poly, gold #D4AF37 accents on deep black #0A0A0A background, no humans, no faces, no text in image, minimal, evocative. Save outputs to `static/img/seed/` (create the folder).

**Aspect ratio + size:** 16:9 at 1K resolution for Space banners and event covers; 1:1 at 1K for post/win/deal covers.

**Generate these 11 images** with the prompts shown:

| Output filename | Aspect | Nano Banana prompt (use verbatim) |
|---|---|---|
| `space-vault.png` | 16:9 | "Abstract minimalist gold geometric vault door, art-deco line work, deep black background, gold #D4AF37 thin lines, no people, no text, evocative of hidden capital and earned access, matte luxury aesthetic" |
| `space-strategy.png` | 16:9 | "Abstract gold chess piece (single rook) merged with architectural blueprint lines, deep black background, gold #D4AF37 only, geometric, minimalist, no people, no text, sharp angles" |
| `space-networking.png` | 16:9 | "Abstract constellation of gold nodes connected by thin lines, deep black background, gold #D4AF37 thin lines, no people, no text, evocative of brotherhood and connection, minimal" |
| `space-investment.png` | 16:9 | "Abstract gold ascending line graph merged with classical column architecture, deep black background, gold #D4AF37 only, geometric, no people, no text, sovereign capital aesthetic" |
| `space-wellness.png` | 16:9 | "Abstract gold geometric figure of human body in motion, sacred geometry overlay, deep black background, gold #D4AF37 thin lines, no faces, no text, vitality and discipline aesthetic" |
| `space-creator.png` | 16:9 | "Abstract gold forge with hammer striking sparks, art-deco line work, deep black background, gold #D4AF37 only, no people, no text, masculine craftsmanship aesthetic" |
| `event-mastermind.png` | 16:9 | "Abstract gold round table seen from above, geometric, deep black background, gold #D4AF37 thin lines, no people, no text, evocative of council and gathering" |
| `event-mixer.png` | 16:9 | "Abstract gold martini glass merged with constellation of intersecting lines, deep black background, gold #D4AF37 only, art-deco, no people, no text" |
| `event-speaker.png` | 16:9 | "Abstract gold geometric microphone on minimalist podium, deep black background, gold #D4AF37 only, art-deco line work, no people, no text" |
| `cover-win.png` | 1:1 | "Abstract gold mountain peak with sun rising behind, deep black background, gold #D4AF37 thin lines, geometric, no people, no text, victory aesthetic" |
| `cover-deal.png` | 1:1 | "Abstract gold geometric handshake formed from architectural lines, deep black background, gold #D4AF37 only, no people, no faces, no text, contract aesthetic" |

After generating, attach images to records:
- Each Space's `cover_image` → corresponding `space-*.png` (path relative to static, e.g., `img/seed/space-vault.png`)
- Each event's `cover_image` → corresponding `event-*.png`
- 30% of seeded Posts → `cover-win.png` or `cover-deal.png` (rotate)
- All seeded Wins → `cover-win.png`
- All seeded Deals → `cover-deal.png`

For **placeholder user avatars** (`profile_photo`): do NOT use Nano Banana — uncanny-valley risk. Generate inline SVG monograms using initials, gold #D4AF37 on black #0A0A0A circle background. Save each as `static/img/seed/avatar-<slug>.svg` and set the user's `profile_photo` to that path.

### 4.3 — Cleanup helper in `seed_placeholders.py`

Add a top-level function `delete_placeholders()` that:
- Deletes all users with email matching `seed.%@sovereign.placeholder` (their cascade-deletes wipe associated content)
- Deletes the generated images in `static/img/seed/`
- Prints a summary

Add a CLI flag: `python seed_placeholders.py --delete` triggers `delete_placeholders()` instead of seeding.

The script must be **idempotent** — running it twice should not duplicate users (check email exists; skip if so).

---

## Step 5 — What NOT to touch

- `_seed_content()` in `app.py` — leave alone.
- `populate_content.py` — leave alone (it's a wrapper for `_seed_content`, separate from your work).
- The existing 6 Spaces, 7 Badges, recurring Events seeded by `_seed_content()` — your placeholder content augments, doesn't replace.
- Any real user accounts that may exist in the DB.
- `templates/` files — Phase 0A handled those.
- `models.py` schema — no migrations in this phase.
- `MEMORY.md` and any auto-memory files — manager session owns those.

---

## Step 6 — Verify

1. Drop into the dev environment fresh DB or test against current dev DB. Run:
   ```bash
   python seed_placeholders.py
   ```
   Expected output: progress lines, summary like "Created 8 users, 16 posts, 4 wins, 4 deals, 7 resources, 1 challenge, 3 events, 11 generated images."

2. Run again immediately:
   ```bash
   python seed_placeholders.py
   ```
   Expected: idempotent — no duplicates, output says "8 users already exist, skipping" etc.

3. Test cleanup:
   ```bash
   python seed_placeholders.py --delete
   ```
   Expected: removes everything including images. Re-run normal seed afterwards to leave the system in seeded state.

4. Start the app:
   ```bash
   python app.py
   ```
   Open `http://localhost:5000/` (log in as one of the placeholder users using its `seed.<slug>@sovereign.placeholder` email — set a known dev password in the script; document it in the script's docstring).

5. Visual check:
   - Feed shows 5+ recent posts with varied authors
   - Each Space loads and shows its generated banner image + 2–3 posts
   - Wins Wall shows 3–4 entries with cover images
   - Deal Board shows 3–4 deals with cover images
   - Resource Vault shows 6–8 entries
   - Member Map shows 8 dots distributed across the US
   - Members page shows 8 members with monogram avatars
   - Events page shows 3 upcoming events with cover images
   - One active weekly challenge visible

6. Confirm no image is photorealistic / no AI faces / all images match the gold-on-black brand.

7. Confirm every placeholder bio ends with `— Founding Voice (pre-launch seed account)`.

---

## Step 7 — Commit + push

Stage exactly:
- `seed_placeholders.py` (new)
- `static/img/seed/` (new directory + all generated images)
- Any test password or credential file you added → DO NOT COMMIT. Use `.gitignore` if needed.

One commit, exact message:

```
phase-0b: seed placeholder community content + imagery

- New seed_placeholders.py: 8 placeholder users (Founding Voice pre-launch
  seed accounts), 16 posts across 6 Spaces, 4 wins, 4 deals, 7 resources,
  1 active weekly challenge, 3 upcoming events
- 11 generated images via Nano Banana (Space banners, event covers,
  win/deal covers) — abstract gold-on-black, no photorealistic people
- Idempotent on re-run; --delete flag for full cleanup
```

Then `git push origin main`.

---

## Step 8 — Update SoT

In `INTEGRATION-SOURCE-OF-TRUTH.md`:

1. §8 Phase Status: add a new row for `0B — Placeholder community seed` and mark it ✅ done with the commit short SHA.
2. §9 Decisions Log: append a new entry dated today summarizing:
   - The placeholder seeding strategy (8 Founding Voice users, deletable by email pattern)
   - The image-generation approach (Nano Banana, abstract gold-on-black, no humans)
   - The cleanup mechanism (`--delete` flag) so future sessions know how to remove seed data before launch
3. §10 Risks: append a new risk: "Placeholder seed content must be cleaned out OR transparently labeled before any paid launch — currently every placeholder user's bio carries `— Founding Voice (pre-launch seed account)` which is honest but visible. Decision needed before public marketing: keep the label as-is, replace with real founder cohort, or delete entirely. Tracked for Phase 1 of the customer journey work."

Commit + push the SoT update separately:

```
sot: phase 0b complete — community seeded with placeholder content
```

---

## Step 9 — Report back to manager

When you return to Kashi, give a 6-bullet summary:

1. Files added (with line counts).
2. DB record counts created (users, posts, wins, deals, resources, etc.).
3. Image count + sample filename list.
4. Sample of one seeded post + one seeded win, pasted in full so the manager can sanity-check the voice.
5. Anything in the existing data model that surprised you (e.g., Resource has no cover_image field, etc.) — flag for follow-up.
6. The exact dev login credentials (placeholder email + password) for the manager to test with — IF you decided to set a shared dev password. If you used per-user passwords or random passwords, document where they live.

If anything in this prompt was ambiguous OR you found that the existing `_seed_content()` already created some of this, STOP and report — do not duplicate.
