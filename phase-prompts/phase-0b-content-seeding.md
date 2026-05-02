# Phase 0B — Seed the Empty Community with Placeholder Content + Imagery

> **v2 — revised after v1 executor stop-and-report.** The Space taxonomy was wrong in v1: the live DB has legacy 6 Spaces (pre-rebrand Skool-shaped names) AND the new 8 sovereign-pilled Spaces from the current `_seed_content()`. Decision (logged in SoT §9, 2026-05-02): **kill the legacy 6 Spaces + legacy 5 Events, canonical set is the 8 sovereign-pilled Spaces and 3 sovereign-voiced Events.** This v2 reflects that.

> Paste this entire prompt into a fresh Claude Code session opened in the local repo. Do not modify the prompt — the manager session sized scope deliberately. This phase MUST come after Phase 0A is committed (verify by `git log --oneline -5` showing `phase-0a:`).

---

## Step 0 — Pull before reading

```bash
git fetch origin && git status
```

If `main` is behind origin: `git reset --hard origin/main` (after confirming no uncommitted local work). The repo lives in iCloud Drive on at least one machine, which causes ref drift; never trust `git pull` alone.

---

## Step 1 — Read first (mandatory)

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — full file. Pay attention to §9 Decisions Log entries from 2026-05-02 (business model, trial, ICP, day-1 features, brand voice, **and the v2 revision decision**).
2. `templates/landing.html` — canonical brand voice (manifesto + 6 pillars + tier names). Match this voice exactly in placeholder copy.
3. `models.py` — full file. Note the field shapes for User, Post, Space, Win, Deal, Resource, WeeklyChallenge, Event, Story, etc.
4. `app.py` lines 281–309 (the `_seed_content()` function) — confirm the 8 sovereign-pilled Spaces it seeds + the 3 Events it creates. Verify whether `_seed_content()` is properly idempotent (should check for existence by name before inserting). If it's NOT idempotent (i.e., adds duplicates on every boot), include a 1-line fix in this phase's commit. **This is the ONLY exception to "do not modify `_seed_content()`."**
5. `populate_content.py` — leave alone, your work goes in a NEW file.
6. Memory: read `~/.claude/projects/-Users-kashikeefe-Library-Mobile-Documents-com-apple-CloudDocs-Desktop-anti-billionaires-app/memory/feedback_copy_no_sobriety_framing.md` if present — applies to ALL placeholder copy in this phase.
7. Live DB inspection — start with:
   ```python
   from app import app, db
   from models import Space, Event
   with app.app_context():
       for s in Space.query.order_by(Space.id).all():
           print(s.id, s.name, s.cover_image)
       for e in Event.query.order_by(Event.id).all():
           print(e.id, e.title)
   ```
   Confirm which IDs are the legacy 6 Spaces vs the new 8, and which Events are legacy vs current. This drives the migration step in 4.0.

---

## Step 2 — Locked context (DO NOT change)

- **Canonical Spaces (8):** Sovereign Wealth, Body & Iron, Awake Minds, Brotherhood Ops, The Arsenal, Red Pill Intel, Family & Legacy, Off Grid.
- **Canonical Events (3):** Fire to Fire (regional in-person), Sovereign Wealth Workshop (monthly), Brotherhood Summit (annual or quarterly).
- **Legacy 6 Spaces** (kill these): The Vault, Business Strategy Room, Networking Lounge, Investment Club, Wellness & Health, Creator's Corner.
- **Legacy 5 Events** (kill these): Weekly Mastermind Call, Monthly Networking Mixer, Guest Speaker: AI Automation, Deal Flow Friday, Wellness Workshop: Peptide Protocols.
- **ICP:** sovereign-pilled men, age 30–50, income $100k–$500k, US-primary. Disillusionment-driven; empty-circle pain secondary.
- **Voice:** masculine, bold, declarative. Match landing.html manifesto cadence ("food is poisoned, money is fake," "build the fire," "operators, builders, protectors").
- **No sobriety/consumption framing.** Do not write any placeholder copy where drinking/sobriety/consumption appears as a metaphor or pain hook.
- **Color palette:** gold #D4AF37 on black #0A0A0A. Every generated image must respect this.
- **Aesthetic:** abstract, geometric, line-art, minimal. **NO photorealistic people, NO faces in any generated image.** Symbols, architecture, geometry, light only.

---

## Step 3 — Goal

The community currently has 14 Spaces (6 legacy + 8 canonical), 8 Events (5 legacy + 3 canonical), 4 Posts, 0 Wins, 0 Deals, 0 Resources, 0 Challenges. After this phase:

- Exactly 8 canonical Spaces remain (legacy 6 deleted).
- Exactly 3 canonical Events remain with cover images (legacy 5 deleted).
- 8 placeholder "Founding Voice" users seeded.
- ~16 posts seeded (2 per Space).
- 4 Wins, 4 Deals, 7 Resources, 1 active Weekly Challenge.
- 13 abstract gold-on-black images generated via Nano Banana.
- `CLAUDE.md` Community Spaces section + Recurring Events section updated to match the new canonical set.
- Everything cleanable via one `--delete` flag.

---

## Step 4 — What to create

### 4.0 — One-time legacy cleanup (RUN FIRST, before any seeding)

Create `seed_placeholders.py` with a `cleanup_legacy_seed()` function that runs at the top of the main seed flow. It must:

1. Delete the 6 legacy Spaces by exact name match: `["The Vault", "Business Strategy Room", "Networking Lounge", "Investment Club", "Wellness & Health", "Creator's Corner"]`. Cascading deletes will wipe their `SpaceMembership`, `Post`, `SpaceChat` rows.
2. Delete the 5 legacy Events by exact name match: `["Weekly Mastermind Call", "Monthly Networking Mixer", "Guest Speaker: AI Automation", "Deal Flow Friday", "Wellness Workshop: Peptide Protocols"]`. Cascading deletes wipe their RSVPs.
3. Delete the orphan PNG files at `static/uploads/space-the-vault.png`, `static/uploads/space-business-strategy.png`, `static/uploads/space-networking-lounge.png`, `static/uploads/space-investment-club.png`, `static/uploads/space-wellness-health.png`, `static/uploads/space-creators-corner.png` (use `os.path.exists` + `os.remove`, do not crash if any are missing).
4. Verify the canonical 8 Spaces exist (created by `_seed_content()` on app startup). If not all 8 exist, log a warning and instruct the operator to run `python populate_content.py` first.
5. Print a summary like: "Legacy cleanup: deleted 6 Spaces, 5 Events, 6 PNG files. Canonical 8 Spaces verified."

**Idempotency:** running `cleanup_legacy_seed()` a second time should be a no-op (legacy items already gone). Do NOT raise errors when deleting already-deleted items.

### 4.0.1 — `_seed_content()` idempotency verification + fix

Read `app.py` lines 281–309. For each `db.session.add(Space(name=...))` call (and similarly for Events), confirm there's a `Space.query.filter_by(name=...).first()` existence check before the add. If ANY space or event creation lacks this guard, add it as a 1-line fix in the same commit. The function must be safe to run on every boot without growing the DB.

If `_seed_content()` is already correct, leave it alone.

### 4.1 — Placeholder users (8)

Single, idempotent seed function. Email pattern: `seed.<slug>@sovereign.placeholder` so all placeholders are deletable in one query. Each user:

| Slug | Name | City | State | Lat, Lng | Specialty | Likely posts in |
|---|---|---|---|---|---|---|
| marcus-w | Marcus W. | Austin | TX | 30.27, -97.74 | Real-estate operator | Sovereign Wealth, Brotherhood Ops |
| james-r | James R. | Miami | FL | 25.76, -80.19 | Macro investor | Sovereign Wealth, Awake Minds |
| sean-t | Sean T. | Coeur d'Alene | ID | 47.68, -116.78 | Strength + nutrition coach | Body & Iron, Family & Legacy |
| brendan-m | Brendan M. | Nashville | TN | 36.16, -86.78 | Builder / contractor | The Arsenal, Off Grid |
| kyle-h | Kyle H. | Jackson | WY | 43.48, -110.76 | Macro / commodities trader | Red Pill Intel, Off Grid |
| anders-l | Anders L. | Bozeman | MT | 45.68, -111.04 | Hardware engineer | The Arsenal, Body & Iron |
| chase-w | Chase W. | Asheville | NC | 35.60, -82.55 | Multi-business operator + father of 3 | Family & Legacy, Brotherhood Ops |
| david-k | David K. | New York | NY | 40.71, -74.01 | Tech founder | Awake Minds, Red Pill Intel |

For each:
- `bio` is 80–140 words, sovereign-pilled, ending on its own line with: `— Founding Voice (pre-launch seed account)`
- `points` between 200 and 4500 (mix of tiers/levels — at least 1 user with `points >= 5000` to populate Platinum tier, at least 2 with Gold)
- `streak_days` between 3 and 45
- `email_verified=True`, `subscription_status="active"`, `referral_code` populated, `created_at` backdated 30–90 days
- `password_hash`: bcrypt of a single shared dev password; document it in the script's docstring (so the manager can log in to verify). Make this a constant at the top of the file: `DEV_SEED_PASSWORD = "ChangeBeforeLaunch_2026!"`. **Do NOT commit this script with a real production password.**
- `profile_photo`: an SVG monogram saved at `static/img/seed/avatar-<slug>.svg` (initials from name, gold #D4AF37 on black #0A0A0A circle). NO Nano Banana for avatars.

### 4.2 — Image generation via Nano Banana (13 images)

Use the `nano-banana-2-skill`. All images: gold #D4AF37 on deep black #0A0A0A, abstract / geometric / line-art, NO humans, NO faces, NO text in image. Output to `static/img/seed/`. Aspect 16:9 at 1K for Space banners + Event covers; 1:1 at 1K for Win/Deal covers.

#### 8 Space banners (16:9 each)

| Filename | Prompt (use verbatim) |
|---|---|
| `space-sovereign-wealth.png` | "Abstract minimalist gold geometric crown floating above a stack of coin discs, art-deco line work, deep black background, gold #D4AF37 thin lines only, no people, no text, sovereign capital aesthetic, matte luxury feel" |
| `space-body-iron.png` | "Abstract gold geometric barbell formed from intersecting architectural lines, sacred geometry overlay, deep black background, gold #D4AF37 only, no people, no text, strength and discipline aesthetic" |
| `space-awake-minds.png` | "Abstract gold sun rising through fractured geometric black surface, art-deco rays, deep black background, gold #D4AF37 thin lines, no faces, no text, awakening and sovereignty aesthetic" |
| `space-brotherhood-ops.png` | "Abstract gold compass rose with intersecting blade-like spokes, art-deco geometric, deep black background, gold #D4AF37 only, no people, no text, operator and brotherhood aesthetic" |
| `space-arsenal.png` | "Abstract gold crossed blades and hammer arranged in geometric art-deco pattern, forge motif, deep black background, gold #D4AF37 thin lines, no people, no text, masculine craftsmanship aesthetic" |
| `space-red-pill-intel.png` | "Abstract gold geometric eye merged with circuit-board line pattern, art-deco style, deep black background, gold #D4AF37 only, no faces, no text, information warfare aesthetic" |
| `space-family-legacy.png` | "Abstract gold geometric tree with branches forming family lineage pattern, art-deco line work, deep black background, gold #D4AF37 thin lines, no people, no text, legacy aesthetic" |
| `space-off-grid.png` | "Abstract gold geometric cabin silhouette beneath constellation of stars and mountain ridge lines, deep black background, gold #D4AF37 only, no people, no text, sovereignty and escape aesthetic" |

#### 3 Event covers (16:9 each)

| Filename | Prompt |
|---|---|
| `event-fire-to-fire.png` | "Abstract gold dual-flame motif with art-deco geometric base, mirrored composition, deep black background, gold #D4AF37 only, no people, no text, brotherhood gathering aesthetic" |
| `event-sovereign-wealth-workshop.png` | "Abstract gold round table seen from above with vault door pattern at center, art-deco geometric, deep black background, gold #D4AF37 thin lines, no people, no text" |
| `event-brotherhood-summit.png` | "Abstract gold mountain summit with constellation of nodes connected at peak, art-deco geometric, deep black background, gold #D4AF37 only, no people, no text, summit aesthetic" |

#### 2 Generic content covers (1:1 each)

| Filename | Prompt |
|---|---|
| `cover-win.png` | "Abstract gold mountain peak with sun rising behind, deep black background, gold #D4AF37 thin lines, geometric, no people, no text, victory aesthetic" |
| `cover-deal.png` | "Abstract gold geometric handshake formed from architectural lines, deep black background, gold #D4AF37 only, no people, no faces, no text, contract aesthetic" |

#### Wire images to records

After generation, write the following relative paths into the DB:

- For each canonical Space (8): `space.cover_image = "img/seed/space-<slug>.png"` — full relative path so `url_for('static', filename=space.cover_image)` resolves correctly. **This implicitly fixes the path bug from the legacy 6.**
- For each canonical Event (3): `event.cover_image = "img/seed/event-<slug>.png"`.
- All seeded Wins (4): `win.image_path = "img/seed/cover-win.png"` (or however the model field is named — verify).
- All seeded Deals (4): `deal.image_path = "img/seed/cover-deal.png"`.
- 30% of seeded Posts: alternate between `cover-win.png` and `cover-deal.png` for visual variety.

### 4.3 — Posts (16 = 8 Spaces × 2 posts)

Two posts per canonical Space, each authored by one of the placeholder users matching that Space's specialty. 80–250 words per post. Voice rules from Step 2 apply. Backdate `created_at` between 60 days ago and 2 days ago, randomized.

Topic seeds (executor: flesh each into a full post in the manifesto voice):

| Space | Author | Topic seed |
|---|---|---|
| Sovereign Wealth | Marcus W. | Why I rotated 30% out of brokerage accounts last quarter and what's replacing it (jurisdictional / tax angle) |
| Sovereign Wealth | James R. | The "compound it forever" meme is propaganda — inflation-adjusted returns since 1971 |
| Body & Iron | Sean T. | 12-week strength block — what hit, what didn't, what I'd do differently |
| Body & Iron | Anders L. | The cheapest performance enhancer is the one nobody trains: rebuilt my sleep architecture in 60 days |
| Awake Minds | David K. | I read Brave New World again at 38. I missed the point at 17. |
| Awake Minds | James R. | Three stories the legacy press buried this week — and why each one matters |
| Brotherhood Ops | Marcus W. | How we ran a 6-man retreat without a coach or agenda — and why nothing got done by accident |
| Brotherhood Ops | Chase W. | Operator stack: the 5 tools I run my businesses on after killing 23 SaaS subscriptions |
| The Arsenal | Brendan M. | The Notion → Obsidian migration that finally stuck — full system + templates |
| The Arsenal | Anders L. | I built my own outreach script after every cold-email tool failed me. 200 lines, here's the architecture. |
| Red Pill Intel | Kyle H. | The CDC's own data on excess mortality 2020–2024, reorganized into a chart they don't show you |
| Red Pill Intel | David K. | Why I stopped reading mainstream economic forecasts — and what I read instead |
| Family & Legacy | Chase W. | How I'm teaching my 7-year-old son to handle a knife. Not metaphor. |
| Family & Legacy | Sean T. | The talk I had with my father at 35 that I should have had at 25 |
| Off Grid | Brendan M. | First six months on 12 acres. What I underestimated — and what was easier than expected |
| Off Grid | Kyle H. | Solar + propane + well: the actual capex breakdown that nobody publishes |

### 4.4 — Wins (4)

Real-sounding outcomes, 60–150 words each, distributed across users. Backdate 7–45 days. Use `cover-win.png` for image. Suggested:
1. Marcus W. — "Closed first off-market deal sourced from this room. $1.4M, 4-cap on the in-place, plenty of meat on the bone for a 5-yr hold. Six months ago I didn't know this asset class existed."
2. Sean T. — "Hit 405 raw squat at 41. Twenty pounds heavier than my college PR. Programming credit goes to the conversation in [Body & Iron] last quarter."
3. Chase W. — "My oldest taught his younger brother how to start a fire without matches this weekend. That's the win."
4. James R. — "Liquidated my last muni-bond position and rotated into hard assets. Seven years late. Felt like cutting an anchor."

### 4.5 — Deals (4)

Mix of categories (`investment`, `partnership`, `service`, `hiring`). 100–200 words each. Use `cover-deal.png` for image. Backdate 5–20 days.

1. **Investment** — Marcus W. — "Looking for 2-3 LPs on a Sun Belt MF syndication. 72-unit B-class, value-add, 16% IRR target, 3-yr term. PM for OM."
2. **Partnership** — Anders L. — "Building a hardware product (off-grid power monitoring) and looking for a fractional founder with B2B distribution chops. Equity, not cash."
3. **Service** — Brendan M. — "Open for one new build project starting Q3 in TN/NC region. Custom homestead, 3-acre+. Brothers get 10% off the GC fee. DM only."
4. **Hiring** — David K. — "Hiring a Sr. Backend engineer for a fintech I'm building (rails: Go + Postgres). Remote OK, US-only. Equity + cash. Brothers first, then I'll open it up."

### 4.6 — Resources (7)

Mix of categories (book, tool, course, podcast, article, template). Real items where possible. 30–80 word descriptions. Each gets at least 2 upvotes from placeholder users.

1. **Book** — "The Sovereign Individual" by Davidson & Rees-Mogg
2. **Book** — "Antifragile" by Nassim Taleb
3. **Book** — "Unscripted" by MJ DeMarco
4. **Tool** — Obsidian (knowledge management — note: link to obsidian.md)
5. **Podcast** — Acquired (Ben Gilbert + David Rosenthal)
6. **Article** — RFK Jr's chronic-disease whitepaper (or similar — pick a real, sovereignty-aligned long-form piece)
7. **Template** — A note about a deal-evaluation framework (no actual file upload — just a description)

### 4.7 — Active Weekly Challenge (1)

7-day challenge starting today, ending in 7 days. Title: **"7-Day Cold Plunge Discipline"**. 200-word description in manifesto voice — physical sovereignty, choosing discomfort, etc. Created by one of the placeholder users (Sean T. fits). Add 2–3 placeholder submissions from other users.

### 4.8 — Event covers ONLY (do NOT create new events)

The 3 canonical Events (Fire to Fire, Sovereign Wealth Workshop, Brotherhood Summit) already exist in DB via `_seed_content()`. Update their `cover_image` field to point at the corresponding generated image:

```python
Event.query.filter_by(title="Fire to Fire - St. Pete").update({"cover_image": "img/seed/event-fire-to-fire.png"})
# Similarly for Sovereign Wealth Workshop, Brotherhood Summit
```

Do NOT create new events. The legacy 5 are deleted in 4.0; the canonical 3 only need cover images.

Add 3–5 placeholder RSVPs (`status="going"`) per event from the placeholder users.

### 4.9 — Update CLAUDE.md

Find the `## Community Spaces (seeded)` section and replace its body with the canonical 8:

```markdown
## Community Spaces (seeded)
1. Sovereign Wealth — capital allocation, macro, deal flow
2. Body & Iron — strength, training, discipline
3. Awake Minds — sovereignty, awakening, contrarian thought
4. Brotherhood Ops — operations, getting things done together
5. The Arsenal — tools, systems, builders' workshop
6. Red Pill Intel — information, signal vs noise
7. Family & Legacy — fatherhood, generations, building for sons
8. Off Grid — physical sovereignty, land, security
```

Find the `## Recurring Events (seeded)` section and replace with:

```markdown
## Recurring Events (seeded)
- Fire to Fire (regional in-person gatherings)
- Sovereign Wealth Workshop (monthly, virtual)
- Brotherhood Summit (annual flagship)
```

### 4.10 — Cleanup helper

Add `--delete` CLI flag to `seed_placeholders.py`. When invoked: deletes all `seed.%@sovereign.placeholder` users (cascade-deletes their content), deletes all images in `static/img/seed/`, prints summary. Idempotent.

---

## Step 5 — What NOT to touch

- `populate_content.py` — leave alone.
- `_seed_content()` in `app.py` — touch ONLY for the idempotency guard fix in 4.0.1. Do NOT change the canonical 8 Space names or the canonical 3 Event names. Do NOT add new ones.
- `templates/` files — Phase 0A handled those.
- `models.py` schema — no migrations in this phase.
- `MEMORY.md` and any auto-memory files — manager session owns those.
- Any real (non-placeholder) user accounts that may exist in the DB. The legacy 6 Space deletion may cascade-delete `SpaceMembership` rows for real users, which is acceptable pre-launch but flag any unexpected hits.

---

## Step 6 — Verify

1. From a fresh state, run:
   ```bash
   python seed_placeholders.py
   ```
   Expected output: legacy cleanup summary, then seed summary. No errors.

2. Run again immediately. Expected: idempotent — "Legacy already clean. 8 users already exist, skipping..." etc.

3. Test cleanup:
   ```bash
   python seed_placeholders.py --delete
   ```
   Expected: removes all placeholders + images. Re-run normal seed afterwards.

4. Start the app:
   ```bash
   python app.py
   ```
   (Per Phase 0A executor's note, port 5000 may be held by macOS Control Center; if so, run `PORT=5050 python app.py`.) Open the app, log in as one of the placeholder users using `seed.<slug>@sovereign.placeholder` + `DEV_SEED_PASSWORD`.

5. Visual check — every page must look right:
   - `/spaces` shows exactly 8 Spaces, each with its banner image rendering (NOT 404'd).
   - Each Space's page (`/space/<id>`) loads, shows its banner, shows 2 posts.
   - `/feed` shows recent posts with varied authors.
   - `/wins` shows 4 wins with cover images.
   - `/deals` shows 4 deals with cover images.
   - `/resources` shows 7 resources.
   - `/members` shows 8 members with monogram avatars.
   - `/map` shows 8 dots distributed across the US.
   - `/events` shows exactly 3 upcoming events with cover images.
   - The active Weekly Challenge is visible.

6. Sanity check — every placeholder bio ends with `— Founding Voice (pre-launch seed account)`.

7. Confirm no generated image is photorealistic / has AI faces / breaks the brand palette.

8. Run a grep to confirm legacy is gone:
   ```bash
   grep -rn -E "(The Vault|Business Strategy Room|Networking Lounge|Investment Club|Wellness & Health|Creator's Corner)" templates/ app.py phase3_routes.py features_routes.py CLAUDE.md INTEGRATION-SOURCE-OF-TRUTH.md 2>/dev/null
   ```
   Expected: no hits in CLAUDE.md or app.py code paths. (Hits in INTEGRATION-SOURCE-OF-TRUTH.md within the v1→v2 revision decision entry are EXPECTED — that's history, leave it.)

---

## Step 7 — Commit + push

Stage exactly:
- `seed_placeholders.py` (new)
- `static/img/seed/` (new directory + all generated images + 8 SVG monograms)
- `CLAUDE.md` (updated Community Spaces + Recurring Events sections)
- `app.py` ONLY if you applied the `_seed_content()` idempotency guard fix in 4.0.1

DO NOT stage:
- `.venv/` (gitignore it if not already)
- Any local DB files (instance/abmc.db)
- Any test/scratch files

One commit, exact message:

```
phase-0b: seed canonical community + kill legacy 6 spaces / 5 events

- Delete legacy 6 Spaces (Vault/Business Strategy/Networking/Investment/
  Wellness/Creator's) and legacy 5 Events (pre-rebrand artifacts)
- New seed_placeholders.py: 8 Founding Voice users, 16 posts across the
  canonical 8 Spaces, 4 wins, 4 deals, 7 resources, 1 active challenge,
  RSVPs on the 3 canonical events
- 13 generated images via Nano Banana (8 Space banners, 3 Event covers,
  2 generic content covers) — abstract gold-on-black, no humans
- Update CLAUDE.md to canonical 8 Spaces + 3 Events
- Idempotent on re-run; --delete flag for full cleanup
```

Then `git push origin main`.

---

## Step 8 — Update SoT

In `INTEGRATION-SOURCE-OF-TRUTH.md`:

1. §8 Phase Status: change Phase 0B row from `⬜ pending` to `✅ done` with the commit short SHA.
2. §9 Decisions Log: append a new entry summarizing what was migrated/seeded, and noting the `_seed_content()` idempotency fix if you applied one.
3. §10 Risks: append an entry: "Placeholder seed content must be cleaned out OR transparently labeled before any paid launch — currently every placeholder user's bio carries `— Founding Voice (pre-launch seed account)` which is honest but visible. Decision needed before public marketing: keep as-is, replace with real founder cohort, or delete entirely. Tracked for Phase 1 of the customer journey work."

Commit + push the SoT update separately:

```
sot: phase 0b complete — community seeded, legacy purged
```

---

## Step 9 — Report back to manager

When you return to Kashi, give a 6-bullet summary:

1. Files added (paths + line counts) and files modified.
2. DB record counts after seeding (Spaces, Events, Users, Posts, Wins, Deals, Resources, Challenges).
3. Image count + filename list.
4. Sample of one seeded post + one seeded win, pasted in full so the manager can sanity-check the voice.
5. Whether `_seed_content()` needed an idempotency fix (yes/no, what changed).
6. Dev login credentials (placeholder email + `DEV_SEED_PASSWORD`) for the manager to test with.

If anything in this prompt is ambiguous OR you find a conflict between this prompt and the SoT, STOP and report — do not make a judgement call.
