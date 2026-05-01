# PHASE — Rebrand to "Sovereign Society" + Active Theory Landing Page

> Drop into a fresh Claude Code session in `~/Desktop/anti-billionaires-app`. Goal: rename the entire app from "The 1% Men's Club" / "anti-billionaires" / "ABMC" to **Sovereign Society** everywhere, AND rebuild the landing page in the Active Theory cinematic WebGL aesthetic (obsidian + iridescent, Fraunces italic, particle field, smooth scroll, post-processing chain). Keep all existing app functionality intact — only the brand surface and landing page change.

## Step 0 — Always Pull Before Reading

```bash
git pull origin main
```

If conflicts, resolve before proceeding. Note any failures and continue.

## Read first

1. `~/Desktop/anti-billionaires-app/INTEGRATION-SOURCE-OF-TRUTH.md` — current project state
2. `~/Desktop/claude-superpowers-v2/PLAN.md` — the canonical Active Theory design brief. This file contains the full visual vocabulary, palette, scene setup, post-processing chain, typography, animations, and chapter mapping. Use it as the design reference.
3. `~/Desktop/claude-superpowers-v2/index.html` and `~/Desktop/claude-superpowers-v2/src/` (if the rebuild is implemented there) — for the actual reference implementation patterns

## Pre-flight

1. `pwd` is `/Users/kenneth/Desktop/anti-billionaires-app`
2. `git status` — note any uncommitted work-in-progress; do not include it in this rebrand commit
3. Capture a list of EVERY file that contains the strings "1% Men's Club", "1% Mens Club", "anti-billionaires", "ABMC", "Anti Billionaires", "anti billionaires" (case-insensitive). Use:

```bash
grep -ril -e "1% Men" -e "anti-billionaires" -e "ABMC" -e "Anti Billionaires" -e "anti billionaires" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=instance .
```

Save that list before any edits — it is the rebrand target inventory.

---

## PART A — Full Rebrand (do this BEFORE the landing page work)

### A1. Decide the new brand strings

**Brand display name:** `Sovereign Society`
**Internal slug / DB / code identifier:** `sovereign-society` (kebab-case for files/URLs), `sovereign_society` (snake-case for Python identifiers), `SovereignSociety` (PascalCase for class names if any)

Confirm with the user if these conventions are wrong before mass-replacing. Otherwise proceed.

### A2. Files to update (apply replacements)

Walk the inventory from pre-flight step 3. Apply replacements appropriately to each file type:

**Python files (`app.py`, `models.py`, `features_routes.py`, `phase3_routes.py`, etc.)**
- "1% Men's Club" / "The 1% Men's Club" → "Sovereign Society"
- "anti-billionaires" / "ABMC" → "sovereign-society" or "Sovereign Society" (pick by context)
- Any SECRET_KEY or env var defaults that include the old brand → update
- Any seed data strings (welcome messages, default badge names, default content) → update

**Templates (`templates/*.html`)**
- All visible copy referencing the old brand → "Sovereign Society"
- All `<title>` tags → "Sovereign Society — <page name>"
- All meta description / OG title / OG description → updated accordingly

**Static files (`static/css/style.css`, etc.)**
- Look for class names that hardcode the brand (e.g. `.abmc-badge`) → consider renaming with a deprecation comment, but DO NOT mass-rename CSS classes (high risk of breaking selectors). Add new classes for new components instead.

**Manifest / PWA**
- `static/manifest.json` (if exists) — update name + short_name + description
- `static/icons/` — note that logos may still say "1%" visually; flag those as needing redesign in PART B but do not touch the image files in this phase

**README, docs, CLAUDE.md, AGENTS.md, MANAGER-PROMPT.md, INTEGRATION-SOURCE-OF-TRUTH.md**
- Update brand references throughout
- Update §1 of INTEGRATION-SOURCE-OF-TRUTH.md to record the rename in §9 Decisions Log AND update the Project Identity section

**`.env.example`**
- Update any default values that referenced the old brand

### A3. Database considerations

Do NOT run migrations in this phase. The DB schema does not encode the brand name. If there is seed data with the old brand (default user posts, system messages), flag for the user — Phase deferred.

If `init_db.py` or `populate_content.py` has hardcoded brand strings, update them so future fresh DB seeds use the new brand.

### A4. Commit the rebrand cleanly

After all replacements:

```bash
git status   # verify ONLY the intended files are staged
git diff --stat   # show count of changes
```

Stage with explicit file globs (NOT `git add -A`). Examples:

```bash
git add app.py models.py features_routes.py phase3_routes.py templates/ README.md CLAUDE.md MANAGER-PROMPT.md INTEGRATION-SOURCE-OF-TRUTH.md
```

Add any other touched files explicitly.

Commit:
```
git commit -m "rebrand: 1% Men's Club → Sovereign Society"
git push
```

---

## PART B — Active Theory Landing Page

### B1. Read the canonical design brief

Open `~/Desktop/claude-superpowers-v2/PLAN.md`. The "Palette," "Scene layer," "HUD," and "Behaviors" sections define the design vocabulary verbatim.

Replicate the same vocabulary, NOT the same copy. Sovereign Society has its own copy + chapters (defined in B3 below).

### B2. Where the landing page lives in this Flask app

The landing page replaces the existing root route. Currently `/` renders `templates/feed.html` (or similar) for logged-in users, and probably some basic landing for logged-out. The redesign:

- Logged-OUT users hitting `/` see the new Active Theory landing page
- Logged-IN users hitting `/` continue to feed (no change)

Add or update the route in `app.py`:
```python
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("feed"))
    return render_template("landing.html")
```

Create `templates/landing.html` as the new Active Theory experience.

### B3. Landing page chapter structure (Sovereign Society edition)

Write copy that is FROM Sovereign Society to its target member. Tone: peer-to-peer, restraint over hype, sovereignty + creator-genius framing. NOT bro-y, NOT crypto-bro, NOT manosphere. Closer to: high-end coaching brand for serious men.

Chapters (each becomes an anchor + scroll section):

1. `#hero` — Brand mark "SOVEREIGN SOCIETY" in italic Fraunces, hero subtitle ("A private society for men who refuse to outsource their lives. Build your zone of genius. Compound it. Live from it."), one CTA ("Apply for membership" → /pricing or /apply)
2. `#manifesto` — Single full-bleed paragraph, italic Fraunces, the brand POV ("We are not here to sell you the next dopamine hit. We are here because the dominant culture has stopped producing men who can lead themselves, let alone anyone else. Sovereign Society is the practice of becoming one of the few who still can.")
3. `#promise` — Three columns / cards in mono caps: "OWN YOUR TIME · OWN YOUR ATTENTION · OWN YOUR OUTPUT." Below each, one tight paragraph.
4. `#what-you-get` — The actual app surface as a feature list (verbatim from the existing app's modules — Spaces, Courses, Wins, Weekly Challenges, Accountability Pairs, Direct Messaging, Calendar Bookings, AI Sidekick, Reels, Stories, Resources Library, Badges/Gamification). Six cards, three rows of two, iridescent borders.
5. `#proof` — Member-results section. If real testimonials/case studies do not exist, use "Coming soon — first cohort wins" placeholder. Do NOT fabricate testimonials.
6. `#pricing` — Anchor to the existing /pricing page (or render the offer inline if simpler). Frame the offer per whatever the user picked in business-model decision.
7. `#apply` — Closing CTA in mono caps, with a magenta underline. Single button → /signup (or /apply if you decide to gate first).

### B4. The Active Theory implementation

Use the same JS stack as the Claude Code Superpowers rebuild:
- Three.js + WebGLRenderer (ACES filmic, warm obsidian clear)
- Iridescent torus ring (TorusGeometry shader)
- Lemniscate ribbon (Catmull-Rom tube)
- Particle field (1600 warm sparks)
- Post-processing: Bloom + ChromaticAberration + Noise + Vignette
- Lenis smooth scroll
- IntersectionObserver chapter reveals

For Sovereign Society SPECIFICALLY:
- The torus ring contains a different glyph — not the fox mascot. Pick one of: a stylized crown, a phoenix silhouette, a triangle with eye, or a simple infinity glyph. Recommend the infinity glyph (clean, brand-neutral, ties to "compound it").
- Color sweep stays violet → magenta → ember → bone (do not invent new palette without asking the user)

### B5. Bundle the static assets into Flask

The Active Theory site is JS-heavy. Place built assets at:
- `static/landing/dist/` — bundled JS
- `static/landing/img/` — any imagery
- `static/landing/audio/` — any audio (likely not needed for landing)

Reference from `templates/landing.html`:
```html
<link rel="stylesheet" href="{{ url_for('static', filename='landing/dist/landing.css') }}">
<script type="module" src="{{ url_for('static', filename='landing/dist/landing.js') }}"></script>
```

Set up a build pipeline if needed (Vite or esbuild) outside this phase if it does not exist. For first pass, you can ship the JS as a single `landing.js` with everything inlined and CDN-loaded three/lenis/postprocessing.

### B6. Build verification (lesson from the Superpowers regression)

Before deploying, verify that index.html (or landing.html) references asset filenames that actually exist on disk. This catches the most common deploy failure mode (HTML references stale bundle hashes from before the latest build).

```bash
# After vite build, extract every asset reference from the built HTML
grep -oE 'static/landing/dist/[a-zA-Z0-9._/-]+\.(js|css)' static/landing/dist/index.html | sort -u | while read path; do
  if [[ -f "$path" ]]; then
    echo "OK: $path"
  else
    echo "MISSING: $path"
    exit 1
  fi
done
```

If anything reports MISSING, the build is corrupted — re-run `vite build` or investigate before deploying. Never push to Railway with broken asset references.

### B7. Verify locally

```bash
flask run   # or however the app is launched
# visit http://localhost:5000/
```

- Landing page loads in a logged-OUT browser
- Logged-in user goes straight to feed
- Smooth scroll works
- Particle field renders without console errors
- Mobile fallback renders the same chapters as a static, scrollable page (no WebGL crash on iOS Safari)

### B8. Commit the landing page cleanly

Stage explicit files only:
```bash
git add templates/landing.html static/landing/ app.py
```

Commit:
```
git commit -m "feat(landing): active theory landing page for sovereign society"
git push
```

---

## Done criteria

- [ ] Every "1% Men's Club" / "anti-billionaires" / "ABMC" string in the codebase replaced with "Sovereign Society" (or the appropriate slug/snake_case)
- [ ] INTEGRATION-SOURCE-OF-TRUTH.md updated with the rename + Decisions Log entry
- [ ] Logged-out `/` renders the new landing page
- [ ] Logged-in `/` still goes to feed (no regression)
- [ ] Active Theory aesthetic visible: obsidian palette, iridescent ring, particle field, smooth scroll, post-processing
- [ ] All 7 landing chapters exist with the copy from B3
- [ ] No invented testimonials or fake stats anywhere
- [ ] Mobile fallback renders without crashing on iOS Safari
- [ ] Two clean commits pushed (rebrand + landing)

## What NOT to do

- Do not touch the database — no migrations, no schema changes in this phase
- Do not rename the GitHub repo or Railway service — separate user decision
- Do not fabricate testimonials, member counts, or social proof
- Do not commit other unstaged work that is in your working tree (only the rebrand + landing files)
- Do not modify auth, payment, or any backend logic
- Do not change the brand color palette without asking the user first (violet → magenta → ember → bone is locked)
- Do not redesign other pages in this phase (only the public-facing `/` landing). Internal pages (feed, profile, spaces, etc.) get their own future phase.

## Report back

- Total files changed in the rebrand
- Any files where the rebrand was ambiguous (manual judgment calls)
- Local screenshot or description of how the landing page looks
- Any compute / build issues encountered
- Suggested next phase (probably: redesign the internal app pages to match the landing aesthetic, or build /apply funnel page in same style)
