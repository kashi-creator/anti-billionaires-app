# Phase 0 — Current State Audit

> Paste this entire prompt into a fresh Claude Code session opened in the local repo. This phase runs **in parallel with Phase 0B** — they touch disjoint files and don't conflict. Discovery + two trivial 1-line bug fixes only. No architectural changes.

---

## Step 0 — Pull before reading

```bash
git fetch origin && git status
```

If `main` is behind origin: `git reset --hard origin/main` (after confirming no uncommitted local work). The repo lives in iCloud Drive on at least one machine, which causes ref drift.

---

## Step 1 — Read first (mandatory)

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — full file. Pay attention to §1 (TBD fields to fill in), §4 (routes inventory — incomplete), §5 (env vars), §6 (GHL state), §10 (known risks).
2. `app.py` — full file. Note line 1709 (port 5000 hardcode — fixing this in Step 4) and line 120-126 (`User.has_active_subscription` rejecting `"trialing"` — fixing this in Step 4).
3. `phase3_routes.py` — list every route registered.
4. `features_routes.py` — list every route registered.
5. `email_send.py` — identify the email service used (Resend, Mailgun, SMTP, etc.) and the configured sender domain.
6. `requirements.txt` — note key dependencies and pinned versions.

---

## Step 2 — Discovery

This is read-only. Gather everything you can; flag what you can't reach.

### 2.1 — Routes inventory

Walk the codebase and produce a complete list of every Flask route, organized by feature area. Output should match the §4 format in the SoT and replace its current incomplete list.

Use this approach:

```bash
grep -rn -E "@(app|features|phase3|[a-z_]+_bp)\.route\(" app.py phase3_routes.py features_routes.py
```

Group routes by area (Auth, Feed, Profile, Spaces, DMs, Stories, Wins, Deals, Resources, Challenges, Events, Courses, Goals, Bookings, Notifications, Pricing/Billing, Admin, API). For each area, list routes with method (`GET`/`POST`/etc.) and a one-phrase description.

### 2.2 — Environment variable audit

Run (if Railway CLI is installed and logged in):

```bash
railway variables 2>/dev/null || echo "RAILWAY_CLI_UNAVAILABLE"
```

If Railway CLI is unavailable: document that, and instead `grep -rn 'os.environ.get\|os.getenv' app.py phase3_routes.py features_routes.py email_send.py models.py` to derive the full list of env vars the code expects. Compare against the SoT's §5 list.

For each env var:
- Name
- Where it's referenced (file:line)
- Default value (if any)
- Required-or-optional in production

### 2.3 — Stripe state

Without exposing secrets, document:
- Is Stripe in **test mode** or **live mode**? Inspect `STRIPE_SECRET_KEY` prefix (`sk_test_` vs `sk_live_`) — describe which mode without printing the key.
- What's the configured `STRIPE_PRICE_ID`? Is it a real price object? (If you have Stripe CLI: `stripe prices retrieve <price_id>` to confirm — but only if `stripe` CLI is installed AND logged into the right account. Otherwise note "needs manual verification by Kashi.")
- Is the Stripe webhook endpoint registered? Find the webhook handler route in `app.py` (likely `/stripe-webhook` or similar). Document the route path + the events it expects to handle.
- Does the webhook actually push to GHL today? (Read code, don't run.) This is the §6 question — confirm or contradict the SoT's current claim that "Stripe webhook handler does not push to GHL."

### 2.4 — GHL state

- What does `ghl_upsert_contact()` actually send? Document the exact JSON shape from `app.py:~111`.
- Where is it called from? `grep -n "ghl_upsert_contact(" app.py phase3_routes.py features_routes.py` — list every call site with the tags applied.
- Is `GHL_API_KEY` set in the local env? (Don't print the key — just `echo "GHL_API_KEY: $([ -n "$GHL_API_KEY" ] && echo SET || echo UNSET)"`.)
- Is `GHL_LOCATION_ID` set? Same pattern.
- If both are set AND a sandbox/test contact email is available, ping GHL's `GET /v2/locations/{locationId}` (or whatever the current GHL API endpoint is) to confirm the location exists and the API key works. If not set, document and skip.

### 2.5 — Deploy state

- Find the Railway project name. Either via `railway status` (if CLI available) or by checking `nixpacks.toml` / `package.json` for hints.
- Document the live URL (TBD field in SoT §1). Try `curl -I` against the URL if known; document the response.
- When was the last deploy? `git log --oneline origin/main -10` shows recent commits — assume Railway auto-deployed each.
- Are there any failing migrations? Check `migrations/versions/` for recent files and verify they ran. Look for `flask db upgrade` references in `nixpacks.toml` or build scripts.
- Is the production DB seeded with `_seed_content()`? (Probably yes since `_seed_content()` runs on app startup, but confirm by checking app.py for the trigger.)

### 2.6 — Email infrastructure state

- What service does `email_send.py` use? (Resend / Mailgun / Postmark / SMTP — read the imports.)
- What sender domain is configured? Look for `FROM` address constants or env vars.
- Are DKIM / SPF / DMARC records likely in place? You can't verify without DNS access, but identify the domain that WOULD need them.
- What email templates exist in `templates/emails/`? List them.

### 2.7 — Database state

- Confirm `DATABASE_URL` source — is the production deploy on Railway Postgres or did it fall back to SQLite? Check `nixpacks.toml` and `railway.json` for hints.
- How many migrations are in `migrations/versions/`? List filenames.
- Are there any `User`-table indexes that look insufficient for production load? (Glance only — flag for later, do not change.)

### 2.8 — Anything else surprising

- Check `cron.py` if present — what jobs run on a schedule? Is the scheduler hooked up in production?
- Check `capacitor.config.json` — is there a real iOS build? What bundle ID? Does it match the legacy `com.onepercentmensclub.app` per CLAUDE.md or has it been renamed?
- Check `static/manifest.json` — PWA manifest state.
- Note any `TODO` / `FIXME` / `XXX` comments in code paths that look launch-blocking.

---

## Step 3 — What NOT to do

- Do NOT modify `_seed_content()`, `models.py`, any template, `phase3_routes.py`, `features_routes.py`. The only allowed code edits in Phase 0 are the two 1-line fixes in Step 4.
- Do NOT print secrets (API keys, webhook secrets, DB passwords). Document presence/absence only.
- Do NOT make any GHL writes (creating contacts, opportunities, etc.). Read-only checks only.
- Do NOT make architectural decisions. If you discover something that needs a decision, flag it for the manager session — don't decide yourself.
- Do NOT touch anything Phase 0B is producing (`seed_placeholders.py`, `static/img/seed/`, the canonical Spaces). Phase 0B is running in parallel.

---

## Step 4 — Trivial bug fixes (only these two)

### 4.1 — Port 5000 hardcode

In `app.py`, find the line near 1709 that reads:
```python
app.run(port=5000)
```
(or similar — exact line number may have shifted). Change to:
```python
app.run(port=int(os.environ.get("PORT", 5000)))
```
Confirm `os` is already imported (it is — line 1 of app.py).

### 4.2 — `has_active_subscription` rejects `"trialing"`

In `models.py:120-126`, find:
```python
@property
def has_active_subscription(self):
    if self.is_admin:
        return True
    if self.lifetime_access:
        return True
    return self.subscription_status == "active"
```

Change the last line to:
```python
    return self.subscription_status in ("active", "trialing")
```

Both fixes are launch blockers per SoT §10.

---

## Step 5 — Update SoT

Append a new top-level section `## 13. Phase 0 Audit Report — 2026-MM-DD` to `INTEGRATION-SOURCE-OF-TRUTH.md` (right above §11 Update Rules; §11 stays the last section). Inside §13, document everything discovered in Step 2 — full routes inventory, env var audit, Stripe state, GHL state, deploy state, email infra state, DB state, surprises.

Also:
- §1 Project Identity: fill in any [TBD] fields you confirmed (Live URL, Railway project name, GHL location ID — if discoverable, otherwise leave [TBD] with a note).
- §4 Routes Inventory: replace with the complete list from 2.1.
- §5 Environment Variables: update the "Currently expected" subsection with the actual list from 2.2.
- §6 GHL Integration: update "What's likely missing" → "What IS missing (confirmed)" based on 2.4.
- §8 Phase Status: change Phase 0 from `⬜ pending` to `✅ done` with the commit short SHA.
- §9 Decisions Log: append an entry summarizing what the audit found, especially anything that changes the Phase 1 plan.
- §10 Risks: append any new risks surfaced during the audit. Strike through with date the resolved bugs (port 5000, `has_active_subscription`) once Step 4 commits land.

---

## Step 6 — Commit + push

Two separate commits:

**Commit 1 — bug fixes:**
```
phase-0: fix port 5000 hardcode + has_active_subscription trial state

- app.py: app.run(port=int(os.environ.get('PORT', 5000)))
- models.py: has_active_subscription accepts both 'active' and 'trialing'
```

Stage exactly: `app.py`, `models.py`. Commit. Then push.

**Commit 2 — audit report:**
```
phase-0: audit report — routes, env, stripe, ghl, deploy, email
```

Stage exactly: `INTEGRATION-SOURCE-OF-TRUTH.md`. Commit. Then push.

Two commits keeps code changes and doc changes separate (cleaner blame, easier to revert one without the other).

---

## Step 7 — Report back to manager

7-bullet summary:

1. **Trivial bugs status** — both fixed and pushed (commit SHA), or any blockers?
2. **Routes** — total count by area; surprises (any duplicate, broken, or stub routes)?
3. **Env** — list of variables set in Railway (names only, no values); list of variables expected by code but NOT set in Railway (that's a launch blocker).
4. **Stripe** — test or live? Webhook configured? Webhook → GHL? `STRIPE_PRICE_ID` valid?
5. **GHL** — API key + location ID set? `ghl_upsert_contact` call sites + tags currently applied?
6. **Deploy** — live URL, last deploy, migration state, deploy health.
7. **Surprises / new launch blockers** — anything found that the manager needs to act on.

If anything in this prompt is ambiguous OR the audit finds something that demands an architectural decision, STOP and report — do not decide.
