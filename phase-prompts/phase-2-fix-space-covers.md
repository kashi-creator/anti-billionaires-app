# Phase 2 — Fix Space cover images on production

> Paste this entire prompt into a fresh Claude Code session opened in `/Users/kenneth/anti-billionaires-app`. **One narrow goal:** make the 8 canonical Space cover images render on the live `/spaces` page. Currently all `cover_image` fields are NULL in production DB even though the image files are deployed and the template would render them correctly if populated.
>
> Surfaced 2026-05-03 by manager session. Root cause confirmed via direct DB query against prod: all 8 Space rows have `cover_image=None`. The local-dev `seed_placeholders.py` script populated them on the dev SQLite, but that script was never run against prod Postgres. `_seed_content()` (which DOES run on every Railway boot) creates the 8 canonical Spaces but does NOT set `cover_image`.
>
> This phase does NOT touch Events — that's a separate Phase 3 prompt running in parallel. Disjoint files.

---

## Step 0 — Pull before reading

```bash
git fetch origin && git status
```

If `main` is behind origin: `git reset --hard origin/main` (after confirming no uncommitted local work).

---

## Step 1 — Read first (mandatory)

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — full file. Pay attention to §1 (live URL `https://anti-billionaires-app-production.up.railway.app`, project owned 90% by Bryce, GHL location email is Bryce's), §9 Decisions Log Phase 0B entry which lists the 8 canonical Spaces and the seeded image files in `static/img/seed/`.
2. `app.py` `_seed_content()` function (around line 280-400) — the existing logic that creates the 8 Spaces on app startup. This is what you'll modify.
3. `templates/spaces.html` lines 14-22 — the rendering template. Verify the `cover_image` field is referenced via `url_for('static', filename=space.cover_image)`. **Do NOT modify this template.**
4. `models.py` `Space` model — `cover_image = db.Column(db.String(300), default=None)`. Schema is fine, no migration needed.
5. `seed_placeholders.py` — see how it currently sets `cover_image` paths (e.g., `img/seed/space-sovereign-wealth.png`). Mirror this pattern in `_seed_content()`.
6. `static/img/seed/` directory — confirm all 8 files exist:
   - `space-sovereign-wealth.png`
   - `space-body-iron.png`
   - `space-awake-minds.png`
   - `space-brotherhood-ops.png`
   - `space-arsenal.png`
   - `space-red-pill-intel.png`
   - `space-family-legacy.png`
   - `space-off-grid.png`

---

## Step 2 — The decisions this phase encodes (manager has locked these)

### 2.1 Cover image path mapping

Hardcoded in `_seed_content()`. Each canonical Space gets exactly one cover image:

| Space name | cover_image path |
|---|---|
| `Sovereign Wealth` | `img/seed/space-sovereign-wealth.png` |
| `Body & Iron` | `img/seed/space-body-iron.png` |
| `Awake Minds` | `img/seed/space-awake-minds.png` |
| `Brotherhood Ops` | `img/seed/space-brotherhood-ops.png` |
| `The Arsenal` | `img/seed/space-arsenal.png` |
| `Red Pill Intel` | `img/seed/space-red-pill-intel.png` |
| `Family & Legacy` | `img/seed/space-family-legacy.png` |
| `Off Grid` | `img/seed/space-off-grid.png` |

### 2.2 Self-healing behavior

`_seed_content()` runs on every gunicorn worker boot. It currently uses an existence check (`Space.query.filter_by(name=...).first()`) before inserting, so it doesn't duplicate. **Modify it to also update `cover_image` if the existing row has it set to NULL.** Pseudocode:

```python
existing = Space.query.filter_by(name=name).first()
if existing:
    # Self-heal: backfill cover_image if it was missed by an earlier seed run
    if not existing.cover_image and canonical_cover:
        existing.cover_image = canonical_cover
        db.session.add(existing)
else:
    db.session.add(Space(name=name, ..., cover_image=canonical_cover, ...))
```

This makes the fix idempotent AND retroactive — the next Railway boot heals the existing 8 NULL rows in prod, and any future fresh deploy comes up with covers populated from row #1.

### 2.3 What does NOT happen in this phase

- Do NOT modify `models.py` (no schema change needed).
- Do NOT modify `templates/spaces.html` (renders correctly already).
- Do NOT touch `seed_placeholders.py` (it's a dev-only script; this phase fixes the prod-running `_seed_content`).
- Do NOT touch any Event-related code, models, templates, or routes — Phase 3 owns the events stack rework.
- Do NOT add any new image files. The 8 PNGs are already in `static/img/seed/`.
- Do NOT change cover image paths for any Space — they're locked in §2.1.

---

## Step 3 — Implementation

In `app.py`, find `_seed_content()` (anchor: starts around line 280, contains a `_canonical_spaces = [...]` list or similar). Two changes:

### 3.1 Add a `cover_image` field to the canonical-spaces data structure

If the spaces are listed as tuples `(name, description)` today, change to `(name, description, cover_image)`:

```python
_canonical_spaces = [
    ("Sovereign Wealth",  "Capital allocation, macro, deal flow",                          "img/seed/space-sovereign-wealth.png"),
    ("Body & Iron",       "Strength, training, discipline",                                "img/seed/space-body-iron.png"),
    ("Awake Minds",       "Sovereignty, awakening, contrarian thought",                    "img/seed/space-awake-minds.png"),
    ("Brotherhood Ops",   "Operations, getting things done together",                      "img/seed/space-brotherhood-ops.png"),
    ("The Arsenal",       "Tools, systems, builders' workshop",                            "img/seed/space-arsenal.png"),
    ("Red Pill Intel",    "Information, signal vs noise",                                  "img/seed/space-red-pill-intel.png"),
    ("Family & Legacy",   "Fatherhood, generations, building for sons",                    "img/seed/space-family-legacy.png"),
    ("Off Grid",          "Physical sovereignty, land, security",                          "img/seed/space-off-grid.png"),
]
```

Match the actual descriptions to whatever's already in `_seed_content()` — don't rewrite descriptions, just add the third tuple element. If the current data is in a different shape (dict, list of dicts, etc.), preserve the shape and add `cover_image` as an analogous field.

### 3.2 Update the seeding loop to set + self-heal cover_image

Find the loop that iterates the canonical-spaces list. Where it does:

```python
existing = Space.query.filter_by(name=name).first()
if not existing:
    db.session.add(Space(name=name, description=description, ...))
```

Change to:

```python
existing = Space.query.filter_by(name=name).first()
if existing:
    if not existing.cover_image:
        existing.cover_image = cover_image
elif not existing:
    db.session.add(Space(name=name, description=description, cover_image=cover_image, created_by=<creator_id>))
```

(Preserve whatever `created_by` value is currently used — likely the first admin user id or a system user. Don't change that.)

The `db.session.commit()` at the end of `_seed_content()` flushes both the new inserts AND the cover_image updates.

---

## Step 4 — What NOT to do

- Do NOT remove the existence check (idempotency must be preserved).
- Do NOT add a "destructive" branch that overwrites a non-null cover_image — only fill in NULLs. A future admin manually changing a cover via UI must not be reverted by `_seed_content()` on the next boot.
- Do NOT print the cover_image paths in startup logs (no SECRET_KEY-level concern, just log noise).

---

## Step 5 — Smoke tests

Local:

1. Delete local `instance/abmc.db` (if present) → `python app.py` → fresh DB with all 8 Spaces, all `cover_image` set.
   ```bash
   rm -f instance/abmc.db
   python app.py &
   sleep 3
   sqlite3 instance/abmc.db "SELECT id, name, cover_image FROM space;"
   kill %1
   ```
   Every row should show a non-NULL cover_image path.

2. With existing local DB that already has the 8 Spaces but `cover_image=None`:
   ```bash
   sqlite3 instance/abmc.db "UPDATE space SET cover_image=NULL;"
   python app.py &
   sleep 3
   sqlite3 instance/abmc.db "SELECT id, name, cover_image FROM space;"
   kill %1
   ```
   Self-heal should re-populate all 8.

3. Visit `http://localhost:<port>/spaces` (logged in as a placeholder user) — all 8 banners render. (Static URLs resolve to `/static/img/seed/space-<slug>.png`.)

Production verification (manual, after deploy):

4. After Railway auto-redeploys this commit, hit `https://anti-billionaires-app-production.up.railway.app/spaces` (logged in as the admin account). All 8 banners should render.

5. Or via API: query the prod DB directly via the same `railway run` + `DATABASE_PUBLIC_URL` pattern used by manager sessions:
   ```bash
   railway run sh -c "DATABASE_URL='$DATABASE_PUBLIC_URL' .venv/bin/python -c 'from app import app; from models import Space; app.app_context().push(); [print(s.name, s.cover_image) for s in Space.query.all()]'"
   ```
   All 8 rows should have non-NULL cover_image.

---

## Step 6 — Update SoT

In `INTEGRATION-SOURCE-OF-TRUTH.md`:

- **§9 Decisions Log** — append: Phase 2 (Space cover image fix) shipped, root cause identified (`_seed_content()` didn't set cover_image; only dev-only `seed_placeholders.py` did, and that wasn't run against prod). Self-heal pattern locked: `_seed_content()` now backfills NULL cover_image fields on existing rows without overwriting non-NULL values.
- **§10 Risks** — if there's an entry about "placeholder seed content must be cleaned out" referencing missing cover images, leave it (different concern). No new risks introduced.

---

## Step 7 — Commit + push

Single commit:

```
phase-2: fix space cover images — _seed_content now self-heals null cover_image

Root cause: _seed_content() created the 8 canonical Spaces but didn't set
cover_image. The dev-only seed_placeholders.py script set them locally but
never ran against prod. Live DB had all 8 Space rows with cover_image=NULL.

Fix: extend _seed_content's canonical-spaces list with cover_image paths,
and add a self-heal branch that backfills NULL cover_image on existing rows.
Idempotent — preserves any non-NULL cover_image set by an admin via the UI.

8 canonical Space banners now render on /spaces in production.
```

Stage exactly: `app.py`, `INTEGRATION-SOURCE-OF-TRUTH.md`. Commit. Push.

---

## Step 8 — Report back to manager

5-bullet summary:

1. **Schema unchanged** — confirmed no migration needed.
2. **Fix shipped** — commit SHA, lines touched in `_seed_content()`.
3. **Self-heal verified** — local test 2 (NULL → populated on boot) passes.
4. **Live verification** — prod DB now shows all 8 Spaces with cover_image set (output of step 5.5 above), `/spaces` renders all banners.
5. **Surprises** — anything unexpected (e.g. a Space row with non-NULL cover_image that pointed at a different path; an admin had manually set a cover; a missing image file; etc.).

If anything in this prompt is ambiguous or you find a non-canonical Space already in prod (a 9th Space, a renamed Space, etc.), STOP and report — do NOT decide.
