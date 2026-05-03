# Sovereign Society (anti-billionaires-app) — Integration Source of Truth

> **Master reference for any Claude Code session that touches this project.**
> Every session reads this file first. Every session updates the relevant section before exiting. Do not skip — the next session depends on it.

---

## 1. Project Identity

- **Brand name:** Sovereign Society (formerly "The 1% Men's Club" / "Anti Billionaires")
- **Repo:** github.com/kashi-creator/anti-billionaires-app
- **Local repo (laptop):** `~/Desktop/anti-billionaires-app`
- **Local repo (Mac mini):** [TBD — clone path]
- **Hosted:** Railway, project `anti-billionaires-app` (id `57e32801-8f3b-4bd1-bccb-8e1c8d72c3f6`), production environment. Two services: `anti-billionaires-app` (web, gunicorn) + `Postgres`. CLI auth working as `kashi@thebreathcoachschool.com` (manager session 2026-05-02).
- **Live URL:** `https://anti-billionaires-app-production.up.railway.app` (Railway auto-generated, HTTP 200 as of 2026-05-02). The audit-noted legacy URL `https://onepercentmensclub.up.railway.app` (still in old `capacitor.config.json` until commit on this date) is bound to nothing — likely from an older deleted project — and is the **sole** reason the audit reported "production is down." That false alarm is now resolved; production has been quietly serving from the auto-generated URL all along. Capacitor config corrected in same-day commit.
- **Custom domain:** [TBD] — recommended target `app.sovereignsociety.com`, gated on Q7 (sender / brand domain lock). Once locked, attach via `railway domain` and re-point `capacitor.config.json` `server.url` to the custom domain.
- **GHL location ID:** [TBD — Phase 1 fills, separate from Stratum's location]. Not in local env.
- **Stripe account:** existing (separate from Stratum)

---

## 2. Tech Stack

- **Framework:** Flask (Python)
- **DB:** SQLAlchemy + PostgreSQL (Railway) / SQLite (dev)
- **Auth:** Flask-Login + bcrypt
- **Payments:** Stripe (subscription model — already wired)
- **CRM/Automation:** GHL (partially wired — see §6)
- **Templates:** Jinja2 server-rendered HTML
- **File uploads:** local `static/uploads/`, 16MB cap (S3 migration recommended later)
- **Background:** threading (no Celery yet — fine for MVP volume)

---

## 3. App Scope (this is a full social platform — much bigger than Stratum)

Major feature areas, each with its own DB models + routes + templates:

- **Users** — auth, profiles, points, streaks, referrals, location, calendar bookings, preferences
- **Social Feed** — Posts, Comments, Likes, Follow
- **Spaces (Groups)** — SpaceMembership, Space Chat, group polls
- **Polls** — Poll, PollOption, PollVote
- **Events + RSVPs**
- **Courses** — Course, Lesson, LessonProgress
- **Onboarding Checklists** — ChecklistItem, UserChecklist
- **Direct Messages** — Conversation, Message
- **Stories (IG-style)** — Story, StoryView
- **Wins** — Win, WinReaction
- **Member-to-Member Deals** — Deal, DealInterest
- **Weekly Challenges** — WeeklyChallenge, ChallengeSubmission, ChallengeVote
- **Resources Library** — Resource, ResourceUpvote
- **Goals + Accountability** — MemberGoal, AccountabilityPair, GoalCheckIn
- **Bookmarks**
- **Gamification** — Badge, UserBadge
- **Reels (video)**
- **AI Chat**
- **Calendar / Bookings** — Availability, CallBooking
- **Activity Feed**
- **Notifications**

---

## 4. Routes Inventory

Verified by Phase 0 audit (2026-05-02). Total: **105 routes** across `app.py` (54) + `phase3_routes.py` (9) + `features_routes.py` (42). Full list — see §13.1 below.

**By area (summary):**
- Public: `/`, `/terms`, `/privacy`, `/pricing`, `/r/<code>` (referral landing)
- Auth: `/login`, `/signup`, `/logout`, `/forgot-password`, `/reset-password/<token>`, `/verify-email/<token>`, `/resend-verification`
- Onboarding: `/onboarding` (GET/POST, 5 steps)
- Feed: `/feed` (GET/POST), `/like/<id>`, `/comment/<id>`, `/post/<id>` (DELETE), `/poll/vote/<id>`
- Profile: `/profile/<id>`, `/profile/edit`, `/members`, `/leaderboard`, `/follow/<id>`, `/profile/location`
- Spaces: `/spaces`, `/space/<id>`, `/space/create`, `/space/<id>/{join,leave,post}`, `/space/<id>/chat`, `/space/<id>/chat/{send,poll}`
- DMs: `/messages`, `/messages/new/<user_id>`, `/messages/<convo_id>`, `/messages/<convo_id>/{send,poll}`, `/api/messages/unread-count`
- Stories: `/stories/create`, `/stories/<id>`, `/api/stories`
- Wins: `/wins`, `/wins/create`, `/wins/<id>/react`
- Deals: `/deals`, `/deals/create`, `/deals/<id>`, `/deals/<id>/interest`
- Resources: `/resources`, `/resources/create`, `/resources/<id>/upvote`
- Challenges: `/challenges`, `/challenges/create`, `/challenges/<id>`, `/challenges/<id>/submit`, `/challenges/submission/<id>/vote`
- Events: `/events`, `/events/<id>`, `/events/create`, `/events/<id>/rsvp`
- Lessons (Vault): `/learn` (alias), `/lessons`, `/lessons/<course>/<lesson>`, `/lessons/<course>/<lesson>/complete`
- Welcome checklist: `/welcome`, `/welcome/check/<id>`
- Goals / Accountability: `/accountability`, `/accountability/pair/<user>`, `/accountability/goals/{create,<id>/checkin,<id>/complete}`
- Bookmarks: `/bookmarks`, `/bookmark/<post_id>`
- Bookings: `/book/<user>`, `/book/<user>/create`, `/bookings`, `/bookings/<id>/{confirm,cancel}`
- Reels: `/reels`, `/reels/create`
- Wingman (AI): `/wingman`, `/wingman/send`
- Map: `/map`
- Boardroom: `/boardroom`
- Misc: `/badges`, `/spotlights`, `/activity`, `/search`, `/referrals`, `/preferences/digest`
- Notifications: `/notifications`, `/notifications/read`, `/notifications/mark-read`, `/api/notifications/unread-count`, `/api/notifications/recent`
- Native (Capacitor): `/api/devices/{register,unregister}`
- Pricing/Billing: `/pricing`, `/validate-code`, `/create-checkout-session`, `/subscription/success`, `/billing-portal`, `/webhook/stripe`
- Admin: `/admin`, `/admin/member/<id>`, `/admin/{toggle-admin,toggle-subscription,grant-lifetime,revoke-lifetime,refund-last,comp-month}/<id>`

**No duplicate routes detected.** Two near-duplicates that are intentional: `/notifications/read` and `/notifications/mark-read` (both POST, both mark-all-read; the second is a leftover; safe to leave but flag for cleanup). The `/learn` route is a 302 redirect alias to `phase3.lessons`.

**Stub / partial routes flagged:**
- `/wingman/send` (`features_routes.py:894`) returns a placeholder reply if `ANTHROPIC_API_KEY` is missing or contains "placeholder"/"replace" — works, but unconfigured in local env. Acceptable for MVP.
- `/create-checkout-session` (`app.py:1237`) returns a 400 with "Payment is not configured yet. Use a founder code to join." if `STRIPE_SECRET_KEY` looks placeholder. Defaults to founder-code path.

---

## 5. Environment Variables

### Currently expected by code (verified by Phase 0 audit, grep across all py files)

| Var | File:line | Default | Required in prod |
|-----|-----------|---------|------------------|
| `FLASK_ENV` | `app.py:40` | `development` | Yes (set to `production`) |
| `SECRET_KEY` | `app.py:41` | none — raises in prod | **Yes — hard requirement** |
| `DATABASE_URL` | `app.py:49` | `sqlite:///abmc.db` | **Yes** (Railway Postgres) |
| `STRIPE_SECRET_KEY` | `app.py:82` | `sk_test_placeholder` | **Yes** (live or test) |
| `STRIPE_PUBLISHABLE_KEY` | `app.py:83` | `pk_test_placeholder` | **Yes** |
| `STRIPE_WEBHOOK_SECRET` | `app.py:84` | `whsec_placeholder` | **Yes** |
| `STRIPE_PRICE_ID` | `app.py:85` | `price_placeholder` | **Yes** |
| `GHL_API_KEY` | `app.py:89` | empty (skip GHL) | Yes (no-op silently if unset) |
| `GHL_LOCATION_ID` | `app.py:90` | empty | Yes (paired with above) |
| `ADMIN_EMAILS` | `app.py:180` | empty (skipped) | Optional (defense-in-depth allowlist) |
| `FOUNDER_CODES` / `FOUNDER_CODE` | `app.py:1231` | `ABMC2026` | Optional (founder bypass codes) |
| `WINGMAN_DAILY_MESSAGE_CAP` | `features_routes.py:873` | `50` | Optional |
| `ANTHROPIC_API_KEY` | `features_routes.py:912` | empty (placeholder mode) | Optional (AI Wingman) |
| `ANTHROPIC_MODEL` | `features_routes.py:919` | `claude-sonnet-4-6` | Optional |
| `RESEND_API_KEY` | `email_send.py:33` | empty (console stub) | **Yes** (transactional email) |
| `EMAIL_FROM` | `email_send.py:21` | `onboarding@resend.dev` | **Yes** (custom sender domain) |
| `EMAIL_FROM_NAME` | `email_send.py:22` | `Sovereign Society` | Optional |
| `PORT` | `app.py:1709` (post-fix) | `5000` | Optional (Railway sets it) |

### Phase 0 verification (2026-05-02)
- **Local shell**: ALL of the above are UNSET in this dev environment. `python app.py` runs with the dev SECRET_KEY warning + sqlite + placeholder Stripe + empty GHL. Acceptable for local; nothing to leak.
- **Railway dashboard**: Railway CLI is installed but not linked from this machine (`railway variables` → "No linked project found"). Manual verification via Railway dashboard required to confirm production env. Phase 1 should run `railway link` once and document.

### Phase 1 additions (consumed by `lib/ghl.py`; all optional, client no-ops if unset)
- `SERVER_NAME` — canonical host for `url_for(_external=True)` outside request context (set in Railway to `anti-billionaires-app-production.up.railway.app` until custom domain locks). Threaded email render needs this.
- `GHL_PIPELINE_ID` — the `Sovereign Society — Member Lifecycle` pipeline id (created in GHL UI by Kashi after Phase 1)
- `GHL_STAGE_PROSPECT_ID`
- `GHL_STAGE_TRIALING_ID`
- `GHL_STAGE_ACTIVE_ID` (active-member)
- `GHL_STAGE_POWER_ID` (power-member)
- `GHL_STAGE_LIFETIME_ID` (lifetime-qualified)
- `GHL_STAGE_AT_RISK_ID`
- `GHL_STAGE_CANCELLED_ID`

### Likely needed in later phases
- `GHL_ONBOARDING_WORKFLOW_ID`
- `GHL_CANCELLATION_WORKFLOW_ID`

---

## 6. GHL Integration — Current State

**Phase 1 (2026-05-02) lifted the inline `ghl_upsert_contact()` to `lib/ghl.py` and locked the canonical tag taxonomy.** The previous "What IS missing" list below now reflects post-Phase-1 state.

### `lib/ghl.py` shape (locked Phase 1)

Single canonical entry point. Public surface:
- `ghl.upsert_contact(*, email, name, phone=None, stage_tag=None, custom_fields=None, extra_tags=None)` — POSTs to `https://services.leadconnectorhq.com/contacts/upsert` with header `Version: 2021-07-28`. Stage tags only (`STAGE_TAGS` set). `ValueError` on any non-canonical tag and on stage tags misrouted into `extra_tags`. Daemon-thread send, fail-silent. No-ops when `GHL_API_KEY`/`GHL_LOCATION_ID` unset.
- `ghl.upsert_opportunity(*, contact_email, stage_tag, monetary_value=99.0)` — Phase 2 stub. Reads `GHL_PIPELINE_ID` + `GHL_STAGE_<NAME>_ID`; logs and returns when env unset (no network call yet).
- `ghl.custom_fields_from_user(user) -> dict` — builds the standard 4-field dict (`payments_made_count`, `qualified_referrals_count`, `lifetime_access` as `"true"`/`"false"`, `lifetime_qualified_at` as ISO date or empty string).
- `ghl.STAGE_TAGS` — frozen set of the 9 canonical stage tags.

Payload JSON:
```json
{
  "email": "<lower>",
  "name": "<display name>",
  "locationId": "<GHL_LOCATION_ID>",
  "tags": ["<one stage tag>", "<extra...>"],
  "phone": "<E.164>",
  "customField": [
    {"key": "payments_made_count", "field_value": "..."},
    {"key": "qualified_referrals_count", "field_value": "..."},
    {"key": "lifetime_access", "field_value": "true|false"},
    {"key": "lifetime_qualified_at", "field_value": "YYYY-MM-DD"}
  ]
}
```

### Canonical Tag Taxonomy (locked Phase 1)

Stage tags only. **Brand tags forbidden** (the GHL location boundary is the brand boundary). A contact carries exactly ONE current-stage tag; the upsert API replaces tags atomically when `tags=` is passed, so old stage tags are swept on each transition.

| Stage | Canonical tag |
|-------|---------------|
| 1 — Prospect | `prospect` |
| 2 — Trialing | `trialing` |
| 3 — Active Member | `active-member` |
| 4 — Power Member | `power-member` |
| 5 — Lifetime-Qualified | `lifetime-qualified` |
| 6 — At-Risk | `at-risk` |
| 7a — Trial-Cancelled | `trial-cancelled` |
| 7b — Member-Cancelled | `cancelled` |
| 8 — Reactivated | `reactivated` |

### Call sites + tags currently applied (post-Phase 1, verified 2026-05-02)

All call sites also pass `custom_fields=ghl.custom_fields_from_user(u)` except `/signup` (free path, no User row yet beyond name/email).

| File trigger | Stage tag | Notes |
|---|---|---|
| `/signup` POST (free signup, no card) | `prospect` | Pure prospect — has account but no payment method. |
| `/signup-with-code` POST (founder-code path) | `lifetime-qualified` | Account is created `lifetime_access=True`. |
| `/subscription/success` POST after Stripe checkout creates account | `trialing` | 30-day trial on file. |
| `customer.subscription.deleted` webhook | `trial-cancelled` (if `payments_made_count == 0`) or `cancelled` | Different win-back audiences. |
| `invoice.payment_succeeded` webhook (every successful charge) | `active-member` | NEW in Phase 1 — keeps custom fields fresh on every payment. |
| `invoice.payment_succeeded` → referrer hits lifetime threshold | `lifetime-qualified` | Referrer's tag flip (paying user gets `active-member` in same handler). |

### What IS still missing (Phase 1 → Phase 2 boundary)

- Webhook coverage gaps remain on `checkout.session.completed`, `customer.subscription.updated`, `invoice.payment_failed` — **Phase 2 scope.**
- Engagement-driven tag transitions (`power-member` on activity threshold, `at-risk` on inactivity, `reactivated` on return) — **Phase 4 scope.**
- No live GHL workflows yet (Kashi sets up in GHL UI separately).
- Pipeline / stage IDs (`GHL_PIPELINE_ID`, `GHL_STAGE_*_ID`) not yet set in Railway env. `ghl.upsert_opportunity()` no-ops until they are.
- `lib/ghl.py` does NOT remove old stage tags explicitly — it relies on GHL's atomic-replace-on-upsert behavior. If GHL's API semantics change, transitions will leak old tags. (Phase 2 should verify against the live GHL location once creds are in.)
- Backfill: `scripts/backfill_ghl_tags.py` is shipped (dry-run by default) but **not yet run against the live GHL location**. Kashi runs `--apply` after reviewing the dry-run output once Bryce shares the location creds.

---

## 7. Customer Journey Stages (membership-flavored, NOT same as Stratum)

| Stage | Tag entry | Description | Channel |
|-------|-----------|-------------|---------|
| 0 — Visitor | (anonymous) | Hits landing page | Pixel + retargeting |
| 1 — Prospect | `prospect` | Email-only lead (lead magnet, referral landing) — no account, no card | Email nurture |
| 2 — Trialing | `trialing` | Signed up with card on file, in 30-day free trial (Stripe status `trialing`) | Onboarding + activation push, day-28 conversion reminder |
| 3 — Active Member | `active-member` + tier-specific | First real charge landed (day 31+, Stripe status `active`) | Engagement loops |
| 4 — Power Member | `power-member` | High activity (posts, course completion, events) | VIP perks, referral push |
| 5 — Lifetime-Qualified | `lifetime-qualified` | Earned lifetime access (3 referrals × 6 paid months each) — billing stopped | Recognition + retention reinforcement |
| 6 — At-Risk | `at-risk` | Low activity 21+ days | Re-engagement |
| 7a — Trial-Cancelled | `trial-cancelled` | Cancelled during 30-day trial, never charged | Different win-back: re-trial offer or testimonial-led re-engagement |
| 7b — Member-Cancelled | `cancelled` | Was paying, cancelled subscription | Standard 3-email win-back over 30 days |
| 8 — Reactivated | `reactivated` | Came back after any cancel | Re-onboarding |

---

## 8. Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| 0 — Current state audit | ✅ done | Routes, env vars, Stripe wiring, GHL wiring, deploy/email/DB state documented in §13. Two 1-line bug fixes shipped in commit `1116d92` (port 5000 hardcode → `PORT` env; `has_active_subscription` accepts `"trialing"`). Audit report committed separately. Surfaced new launch-blockers: production currently 404s, `cron.py` digest references nonexistent fields, brand-tag inconsistency in GHL calls. |
| 0A — Public copy + Terms alignment with locked business model | ✅ done | Rewrite landing.html FAQ #2/#5/#6, fix pricing.html ($100 → $99, add trial + lifetime mechanic), rewrite legal.html Terms §2 with proper subscription disclosure. Prompt at `phase-prompts/phase-0a-copy-terms-alignment.md` — completed 2026-05-02, commit e4aa7fc |
| 0B — Seed empty community with placeholder content + imagery | ✅ done | 8 Founding-Voice users, 16 posts (2 per canonical Space), 4 wins, 4 deals, 7 resources (+14 upvotes), 1 active challenge (+3 submissions), 14 RSVPs across the 3 canonical events. 13 Nano Banana images + 8 SVG monogram avatars. Legacy 6 Spaces + 5 Events purged. Idempotent re-run + `--delete` flag. Completed 2026-05-02, commit 78f8f47. `_seed_content()` idempotency was already correct — no `app.py` change needed. |
| 0C — Wire founder-code onboarding (server side) | ✅ done | New `POST /signup-with-code` route creates a fully-active lifetime account from a valid founder code (lifetime_access=True, subscription_status=active, email_verified=True, lifetime_qualified_at set, is_admin=False). `_is_founder_code()` helper extracted in `app.py`; `/validate-code` refactored onto it. `templates/pricing.html` JS now branches the main CTA on `dataset.founder` — code-applied path swaps the email field for a 3-input mini-form (name/email/password) and submits to `/signup-with-code`; Stripe path unchanged. CSRF meta tag added to `templates/base.html` head; `require_csrf` decorator extended to also accept the `X-CSRFToken` header so JSON fetch callers can pass the token without form-encoding. GHL push uses legacy tags `["Lifetime", "ABMC"]` — Phase 1 will sweep to canonical taxonomy. `send_lifetime_unlocked` called with graceful degrade (try/except + RESEND console fallback). Smoke-tested locally on Flask 3.0 / port 5055/5056: pricing.html serves CSRF meta, validate-code valid+invalid, signup-with-code validates required fields / 10-char password / valid code / duplicate email; success path returns `{"redirect": "/welcome"}` and DB user has all four field flips correct; CSRF header enforcement works (missing header → 400); rate-limit `5/min` confirmed; logged-in lifetime user gets HTTP 200 on `/feed` (no paywall); `/billing-portal` 302-redirects to `/pricing` for lifetime account (no Stripe customer) without crashing; email stub printed to stdout. Completed 2026-05-02. |
| 1 — Lift GHL into proper client + tighten existing integration | ✅ done | `lib/ghl.py` shipped (commit `99cc51b`); `cron.py` field bugs fixed (commit `e5ffdaf`); `scripts/backfill_ghl_tags.py` + SoT updated. 9-tag canonical taxonomy locked; 5 call sites migrated; 4 custom fields sync; SERVER_NAME / PREFERRED_URL_SCHEME wired. Backfill script NOT executed against live — Kashi runs `--apply` separately. Completed 2026-05-02. |
| 2 — Stripe → GHL webhook flow | ⬜ pending | On subscription created/updated/cancelled, mirror to GHL contact + opportunity in Member pipeline |
| 3 — Member intake / first-day onboarding journey in GHL | ⬜ pending | Welcome email, profile completion prompts, content discovery, first-7-days nurture |
| 4 — Engagement automations | ⬜ pending | Tag application on post created, course completed, win posted, event RSVP — drives nurture and gamification |
| 5 — Cancellation / win-back | ⬜ pending | Trigger on subscription cancelled, 3-email win-back sequence over 30 days |
| 6 — Customer Journey Playbook (community context) | ⬜ pending | Membership-flavored playbook (not e-commerce like Stratum) |
| 7 — Compliance + community guidelines | ⬜ pending | Content policy, terms, COPPA if any minors, payment compliance |

---

## 9. Decisions Log

- **2026-05-02 — Business model locked.** Ongoing $99/month subscription, no fixed end. Lifetime access is earned via referrals: when 3 of a member's referrals EACH complete 6 paid months (6 × $99 = $594 per referral), the referring member's billing stops permanently and access becomes lifetime. The `User.payments_made_count`, `User.qualified_referrals_count`, `User.lifetime_access`, and `User.lifetime_qualified_at` fields in `models.py` already reflect this model — no schema change needed. Phase 2 (Stripe → GHL webhook) and Phase 1 (GHL pipelines/tags) must encode this rule: tag `lifetime-qualified` when `lifetime_access` flips to true; tag referrals on each successful payment milestone (1, 3, 6 paid months) so referrers get progress notifications.
- **2026-05-02 — Free trial model locked.** 30-day free trial, **card required at signup** (Stripe `subscription_data.trial_period_days = 30`). Auto-bills on day 31. No "free account without card" path — every signed-up user has a payment method on file. Implications: (1) Stripe subscription status during trial is `"trialing"`, NOT `"active"` — Phase 0 must update `User.has_active_subscription` in `models.py:120-126` to accept both `"active"` and `"trialing"` or trial users will be paywalled out immediately. (2) §7 (Customer Journey) updated to add `trialing` stage and split `cancelled` into `trial-cancelled` (day 1–30, never charged) vs `cancelled` (paid at least once). These are different win-back audiences with different messaging. (3) `User.payments_made_count` only increments on successful real charges (day 31+), so trial months do NOT count toward referrer qualification — this is intentional and aligns with the locked business model.
- **2026-05-02 — Canonical brand positioning locked from existing landing.html.** No new copy will be drafted. The hero ("For the men who refused to be average."), eyebrow ("Sovereign Society — by application only"), manifesto ("engineered reality" → "build the fire"), 6 pillars (Deal Flow / Accountability / Mastermind Calls / The Vault / The Map / The Boardroom), tier names (Bronze/Silver/Gold/Platinum), and final CTA ("The door is open. Walk through it.") in `templates/landing.html` ARE the brand voice. Future copy work pulls from this source. Voice rule: no sobriety/consumption framing. **Discovered during this lock**: landing.html FAQ + pricing.html + legal.html all describe a DIFFERENT business model than what was locked earlier (they say "$99/mo for 3 months → lifetime"). All three need rewriting to match the actual locked model — that's Phase 0A.
- **2026-05-02 — Phase 0A scoped.** Three files have stale/wrong public copy that must be reconciled with locked Q1+Q2 before any marketing or signup activity: `templates/landing.html` (FAQ #2/#5/#6), `templates/pricing.html` ($100 typo → $99, add trial + lifetime referral mechanic), `templates/legal.html` Terms section 2 (Membership clause currently misrepresents the offer — material contract-law exposure). Phase prompt written at `phase-prompts/phase-0a-copy-terms-alignment.md`. Per Kashi: agreement must explicitly disclose the 6-month commitment math per referral.
- **2026-05-02 — ICP locked (TENTATIVE — revisit after first ad campaign data).** Per Kashi: "go with whatever sounds best for now and we can always fix this later." (1) **Primary trigger pain: disillusionment / awakening** — buyer recently red-pilled on food/money/media/state, can't unsee it, looking for a brotherhood of men who already see it. Aligns with the existing manifesto voice on landing.html. Acquisition lives in sovereignty-adjacent creator audiences (RFK Jr / Tucker Carlson / Joe Rogan / Calley Means / Bret Weinstein-adjacent). (2) **Secondary trigger pain: empty circle** — D-buyers typically lose their old social ties; this is the soft-landing copy angle. (3) **Age band: 30–50.** Below 30 can't afford $99 + 3 referrals; above 50 is harder cold-traffic. (4) **Income band: $100k–$500k/year.** Below can't refer; above is already in YPO/EO. (5) **Geography: US primary, UK/CA/AU secondary, non-English markets skip for v1.** Why NOT pain (B) deal-flow / (C) fathers / (E) plateau-successful: B too narrow, C requires manifesto pivot, E is overcrowded with men's-coach competitors. **Revisit trigger:** after the first $5–10k of ad spend, look at which creator audiences and which copy variants converted and re-lock based on real data.
- **2026-05-02 — Day-1 launch-blocker feature set locked (TENTATIVE).** Per Kashi: "fix later" delegation. **Must-work-end-to-end (any bug = launch blocker):** signup → Stripe trial → paywall access flow (incl. `has_active_subscription` fix); feed post/comment/like; DMs; Spaces (join/post/chat — 6 already seeded); profile editing; Stripe billing portal + cancellation; Member Map (distinctive, sells the brand); Events / Mastermind Calls RSVP (1–2 seeded events at launch); notifications; referral system (it IS the business model); pricing + Terms pages (Phase 0A). **Must-work-but-launch-empty (organic content fills):** Deal Board, Resource Vault, Wins Wall, Accountability goals. **Nice-to-have-skippable-at-launch:** Stories, Reels, Weekly Challenges, AI Wingman, Badges (compute lazily), Activity feed, full-text search. Phase 0 audit confirms which of these actually work end-to-end vs which need fixes. Phase prompts for individual fixes will reference this list.
- **2026-05-02 — Phase 0B v1 → v2 revision. Canonical Spaces locked at 8, canonical Events at 3.** Phase 0B v1 prompt assumed CLAUDE.md's documented 6 Spaces. v1 executor stop-and-reported because the live DB actually has 14 Spaces (legacy 6 from a pre-rebrand seed run + new 8 from the current `_seed_content()` in `app.py:281-309`) and 8 Events (legacy 5 + current 3). Per Kashi: kill the legacy 6 Spaces and legacy 5 Events; canonical set is **the 8 sovereign-pilled Spaces** (Sovereign Wealth, Body & Iron, Awake Minds, Brotherhood Ops, The Arsenal, Red Pill Intel, Family & Legacy, Off Grid) and **the 3 sovereign-voiced Events** (Fire to Fire, Sovereign Wealth Workshop, Brotherhood Summit). Side effect: pre-existing `cover_image` path bug on the legacy 6 (`templates/spaces.html:16` resolved bare filenames against `/static/` while files lived in `/static/uploads/`) auto-resolves when legacy is deleted and new banners use full relative paths (`img/seed/space-<slug>.png`). v2 prompt at `phase-prompts/phase-0b-content-seeding.md` overwrites v1; git history preserves v1. v2 also includes a one-line `_seed_content()` idempotency-guard verification + fix (only if needed) so the DB doesn't grow on each boot, and updates `CLAUDE.md` Community Spaces + Recurring Events sections to reflect the canonical set.
- **2026-05-02 — Phase 0B complete (commit 78f8f47).** Community seeded, legacy purged. **Migrations:** legacy 6 Spaces (The Vault / Business Strategy Room / Networking Lounge / Investment Club / Wellness & Health / Creator's Corner) deleted; legacy 5 Events (Weekly Mastermind Call / Monthly Networking Mixer / Guest Speaker: AI Automation / Deal Flow Friday / Wellness Workshop: Peptide Protocols) deleted; 6 orphan PNG files in `static/uploads/` removed. Live DB went from 14→8 Spaces and 8→3 Events. **Seeded:** 8 placeholder users (Marcus W., James R., Sean T., Brendan M., Kyle H., Anders L., Chase W., David K.) at `seed.<slug>@sovereign.placeholder` with shared dev password `ChangeBeforeLaunch_2026!`; tier mix is 1 Platinum / 3 Gold / 3 Silver / 1 Bronze; cities span US for Member Map distribution. 16 posts (2 per canonical Space), 4 wins (Win cover wired), 4 deals (Deal cover wired, mix of investment/partnership/service/hiring), 7 resources (with 14 upvotes), 1 active "7-Day Cold Plunge Discipline" challenge (+3 submissions), 14 RSVPs across the 3 canonical events. **Imagery:** 13 abstract gold-on-black PNGs via Nano Banana (8 Space banners + 3 Event covers @ 16:9 1K, 2 generic content covers @ 1:1 1K) saved to `static/img/seed/`; 8 SVG monogram avatars (gold initials on black) generated locally. All `cover_image` fields use full relative paths (`img/seed/space-<slug>.png`) so `url_for('static', ...)` resolves correctly — also implicitly resolves the legacy `templates/spaces.html:16` path bug. **`_seed_content()` idempotency:** verified correct as-is at `app.py:281-396` (existence-checks via `Space.query.filter_by(name=...).first()`, same for Events and Posts) — no fix needed, `app.py` not touched. **CLAUDE.md** Community Spaces + Recurring Events sections updated to canonical 8/3. **Hygiene:** `seed_placeholders.py` is fully idempotent (re-run is no-op) and supports `--delete` flag that wipes all `seed.*` users (cascade), the active challenge, and every image in `static/img/seed/`. Smoke test on local Flask (port 5000 — Control Center wasn't actually holding it tonight; PORT=5050 ignored by `app.py:1709` hardcode, see §10 risk): `/feed`, `/spaces`, `/wins`, `/deals`, `/events`, `/members`, `/resources`, `/map`, `/space/<id>` all return 200 when logged in as a placeholder; all 8 canonical Space banners render via `<img>` tag in `/spaces`.
- **2026-05-02 — Phase 0 audit complete (bug-fix commit `1116d92`; audit-report commit follows immediately).** Two 1-line launch-blocker bugs fixed: `app.py:1709` now reads `port=int(os.environ.get("PORT", 5000))` (Railway sets `PORT`; macOS Control Center holds 5000 locally so the env-var path is needed in dev too); `models.py:120-126` `has_active_subscription` now accepts `"active"` OR `"trialing"` (locked 30-day trial model would have paywalled out every new signup). Discovery surfaced **three new launch blockers** that were not in §10 before — see §10 additions: (1) production at `https://onepercentmensclub.up.railway.app` returns Railway-edge 404 fallback (`x-railway-fallback: true`) on every probed path — service is unbound or paused; nothing is currently serving the app; (2) `cron.py:64,75-77,82` references `Win.content` and `Event.starts_at` neither of which exist on the actual models (Win has `title`+`description`, Event has `date`+`time`) — the weekly digest CLI command will throw `AttributeError` on first run; (3) GHL tags are split between legacy `"ABMC"` and new `"Sovereign Society"` strings across 4 call sites — Phase 1 must standardize before any lifecycle automations are wired. Also a **factual correction to §6**: prior text said "Stripe webhook handler does not push to GHL" — that is no longer true. The webhook DOES push to GHL on subscription cancel (Churned) and on lifetime unlock (Lifetime). It does NOT push on checkout-completed, sub-updated, payment-succeeded (non-lifetime branch), or payment-failed; Phase 2 widens the coverage. Routes inventory locked at 105 (54 in `app.py`, 9 in `phase3_routes.py`, 42 in `features_routes.py`) — full list in §13.1.
- **2026-05-02 — Phase 0C: founder-code onboarding semantics locked.** A valid founder code (entered on `/pricing`'s "Have a code?" panel) grants the entered email a fully-active lifetime account with no payment and no email-verification step: `User.lifetime_access=True`, `subscription_status="active"`, `lifetime_qualified_at=datetime.utcnow()`, `email_verified=True`, `is_admin=False` (admin status remains a manual flip in `/admin`, NOT carried by the code itself — keeps the code from being an admin-escalation vector if leaked). Code source: single `_is_founder_code()` helper in `app.py` reads `FOUNDER_CODES` (or legacy singular `FOUNDER_CODE`) with default `ABMC2026`; `/validate-code` and `/signup-with-code` both go through the helper. UX: when validate-code returns valid, pricing.html swaps the email field for a 3-input mini-form (name/email/password) and rebinds the main CTA via `dataset.founder='true'` to call `/signup-with-code`; Stripe path stays untouched. GHL push uses legacy tags `["Lifetime", "ABMC"]` — consistent with the rest of current call sites; Phase 1 will sweep all four call sites to the canonical `lifetime-qualified` taxonomy in one shot. Welcome email reuses `send_lifetime_unlocked` (template fits semantic state); RESEND degrade path prints to stdout (graceful). CSRF: `require_csrf` decorator extended to also accept `X-CSRFToken` header so JSON fetch callers don't need to form-encode; `templates/base.html` now carries a `<meta name="csrf-token">` tag for client-side reads. Rate limit: `5/min` per IP, matches `/signup`'s posture. Implementation commit: phase-0c shipped on main.
- **2026-05-02 — Phase 1 complete (commits `99cc51b` + `e5ffdaf` + backfill/SoT commit).** GHL lift + tag taxonomy + cron.py fixes + threaded-email-render fix shipped together. **Lift:** `lib/__init__.py` + `lib/ghl.py` created; the inline `ghl_upsert_contact` (formerly `app.py:227-258`) and its `GHL_API_KEY`/`GHL_LOCATION_ID` module-level constants are gone; orphaned `requests` and top-level `threading` imports removed. New surface: `ghl.upsert_contact(*, email, name, phone=None, stage_tag=None, custom_fields=None, extra_tags=None)`, `ghl.upsert_opportunity(*, contact_email, stage_tag, monetary_value=99.0)` (Phase 2 stub), `ghl.custom_fields_from_user(user)`, `ghl.STAGE_TAGS`. Daemon-thread send + fail-silent + env-unset no-op preserved. Validation runs BEFORE the env-unset check so misuse fails loudly even in dev. **Tag taxonomy locked at 9 stage tags:** `prospect`, `trialing`, `active-member`, `power-member`, `lifetime-qualified`, `at-risk`, `trial-cancelled`, `cancelled`, `reactivated`. Brand tags (`ABMC`, `Sovereign Society`, `Founder`, `Paid Member`, `Churned`, `Lifetime`) are explicitly rejected with `ValueError`. Stage tags routed via `extra_tags=` are also rejected (caller-mistake guard). **5 call sites migrated:** (1) `/signup` → `prospect`; (2) `/signup-with-code` → `lifetime-qualified` + `custom_fields`; (3) `/subscription/success` → `trialing` + `custom_fields`; (4) `customer.subscription.deleted` → `trial-cancelled` if `payments_made_count == 0` else `cancelled` + `custom_fields`; (5) `invoice.payment_succeeded` non-lifetime → `active-member` + `custom_fields` (NEW — Phase 0 audit gap closed; Phase 2 widens further); (5b) `invoice.payment_succeeded` lifetime branch → referrer gets `lifetime-qualified` + `custom_fields` and the paying user gets the `active-member` push from the same handler. **4 custom fields sync** (`payments_made_count`, `qualified_referrals_count`, `lifetime_access` as `"true"`/`"false"`, `lifetime_qualified_at` as ISO date or empty). **`cron.py` 3 bugs fixed:** `_build_digest_data` builds `f"{w.title} - {w.description}"` for the dict's `content` key (the template still reads `content`); `Event.starts_at` swapped to `Event.date` filter/order with `Event.time` appended to the display string; `cli_test_email` does an explicit early-return + `click.echo` when no admin exists. Smoke-tested locally on Flask 3.0 / port 5099: all 9 prompt smoke tests pass; logged-in `/feed` and `/api/notifications/unread-count` both 200; `flask cron digest` runs to completion (with `SERVER_NAME` set for the URL render); `flask cron test-email` prints the friendly message. **`SERVER_NAME` + `PREFERRED_URL_SCHEME`:** added to `app.config` near MAX_CONTENT_LENGTH; defaults to None in dev (preserves localhost binding) and `anti-billionaires-app-production.up.railway.app` in production unless `SERVER_NAME` env var overrides. **Backfill script:** `scripts/backfill_ghl_tags.py` shipped (default `--dry-run`, requires `--apply` for actual writes; `--throttle-ms` cushion); `scripts/README.md` documents it. NOT executed against live GHL — Kashi runs `--apply` after Bryce shares location creds. **What did NOT happen this phase (Phase 2/4 scope):** webhook coverage on `checkout.session.completed`, `customer.subscription.updated`, `invoice.payment_failed`; engagement-tagging (post/win/event); live GHL workflows; pipeline / stage IDs (env-var contract is in place but values not yet set on Railway). **Net surprise discovered during Step 3.5:** `/create-checkout-session` (`app.py:1348`) does NOT pass `subscription_data={"trial_period_days": 30}` — every Stripe-path signup auto-bills on day 1, contradicting the locked 30-day trial model and the public Terms §2 / FAQ #2. Logged in §10 as a fresh launch blocker.
- **2026-05-02 — Phase 0A complete (commit e4aa7fc).** Public copy + Terms reconciled with locked business model. Three files edited: `templates/landing.html` (FAQ #2/#5/#6 rewritten), `templates/pricing.html` ($100→$99, +trial banner under tagline, +lifetime referral note under cancel-anytime), `templates/legal.html` (§2 expanded into Membership & Billing, new §2A Lifetime Access — Referral-Earned). Repo-wide grep for residual stale copy (`99/month for|three months|three payments|3 payments|3 months`) returned clean. Verified live on local Flask (port 5050; macOS Control Center holds 5000) — `/`, `/pricing`, `/terms` all 200; section ordering reads 1, 2, 2A, 3, 4, 5, 6, 7, 8 as specified. **Final FAQ #2 wording (canonical, quote verbatim in future copy):** "$99 / month, ongoing. Your first 30 days are free — you sign up with a card on file but no charge hits until day 31. There is no fixed end to the membership; you can cancel any time. The Society also offers Lifetime Access — but you don't buy it, you earn it. Bring three brothers into the Society. Once each one has completed six paid months ($594 each), your billing ends permanently and your seat is yours for life." **Final Terms §2A wording (canonical, contract-law load-bearing):** "Sovereign Society offers Lifetime Access at no further charge to members who successfully refer at least three (3) other paying members, where each of those three referrals must independently complete six (6) consecutive months of $99 payments — a total of $594 paid by each referral, or $1,782 in total referral-driven revenue, before the referring member qualifies. Once you reach this threshold, your $99 monthly billing will be permanently terminated and your platform access becomes Lifetime, contingent on continued adherence to the Member Code of Conduct (Section 4). The following do NOT count toward referral qualification: trial-period months (no payment was made); refunded payments; charged-back payments; payments made by referrals who later cancelled before reaching six successful payments. If a referral cancels before completing six payments, their progress does not transfer and is not bankable for a future re-signup. There is no other path to Lifetime Access. Statements elsewhere on the website that may have suggested an alternative path are superseded by this Section."

---

## 10. Known Risks / Open Questions

- **[2026-05-02 audit gap]** The Phase 0 audit missed that `templates/pricing.html`'s founder-code UI had no server-side handler. The "Apply" button validated the code via `/validate-code` and re-styled the CTA, but clicking the CTA still routed to `/create-checkout-session` — which short-circuits to "Payment is not configured" when Stripe placeholder is set. Net effect: every visitor who entered a valid founder code hit a dead end. Resolved by Phase 0C in same-day commit (new `/signup-with-code` route + helper + UX branch). Lesson for future audits: route-grep + env-check is necessary but not sufficient — full UI flows must be smoke-tested end-to-end (click each CTA, confirm the network call hits a real handler, confirm the handler creates the expected side effect). Phase 1 audit checklist should encode this.
- **GitHub PAT exposed in git remote URL** (verified earlier) — needs rotation
- ~~**Inline GHL function in app.py** — refactor to `lib/ghl.py` in Phase 1 for testability~~ (resolved 2026-05-02 by phase-1, see §6 + Decisions Log)
- **No Celery** — background tasks use threading. Fine for MVP, watch for race conditions
- **File uploads stored on Railway disk** — Railway disks are ephemeral on deploys; migrate to S3/R2 before launch
- **Stripe subscription cancellation handling** — needs verification (does the app actually downgrade access on cancel?)
- ~~**`User.has_active_subscription` rejects `"trialing"` status** ([models.py:120-126](models.py#L120-L126)) — current code only treats `"active"` as active. With the locked 30-day-trial model, every trial user will be paywalled out the moment they sign up. **Launch blocker.** Phase 0 fixes this — change to `self.subscription_status in ("active", "trialing")`.~~ (resolved 2026-05-02 by phase-0, commit `1116d92`)
- ~~**Public copy misrepresents the offer.** `templates/landing.html` (FAQ), `templates/pricing.html` ($100 typo + missing trial/lifetime), and `templates/legal.html` (Terms §2) all promise "$99/month for 3 months → lifetime" — a model the code does not implement and which Kashi has confirmed is NOT the actual offer. **Material contract-law exposure if signups happen against this text.** Launch blocker. Phase 0A reconciles all three files.~~ (resolved 2026-05-02 by phase-0a, commit e4aa7fc)
- **Stale support email `support@onepercentmensclub.com`** in `legal.html` (Terms §8 + Privacy §"Your Rights"). Old brand. Need new support email on `sovereignsociety.com` or another chosen domain — depends on Q7 (email sender domain). Cleanup once domain locked.
- ~~**Port 5000 hardcoded in `app.py:1709`.** Surfaced 2026-05-02 by Phase 0A executor — macOS Control Center holds port 5000, blocking local dev. Fix: change `app.run(port=5000)` to `app.run(port=int(os.getenv("PORT", 5000)))`. Trivial 1-line fix, fold into Phase 0 audit.~~ (resolved 2026-05-02 by phase-0, commit `1116d92`)
- **`legal.html` Terms §4 (Member Code of Conduct) is still placeholder text** ("Members agree to engage respectfully…"). The new §2A invokes it as a contingency for Lifetime Access continuation, so when §2A goes live, §4 needs real, enforceable conduct rules. Phase 7 (Compliance + community guidelines) work.
- **`legal.html` `Last updated: April 2026` date is stale** (actual content was updated 2026-05-02 by Phase 0A). Needs a refresh, plus a forward decision on whether to track legal-page revision history (changelog at top of file, archived versions, etc.). Cleanup before any paid signup.
- **Multiple Stripe price IDs?** — one tier today (`STRIPE_PRICE_ID`) — might need annual + monthly + founder pricing
- **GHL location separate from Stratum's** — must NOT cross-contaminate contact data between businesses
- **Repo lives in iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/Desktop/anti-billionaires-app`).** iCloud syncs both the working tree AND the `.git` folder, which causes ref drift between machines (observed 2026-05-02: local `main` was 10 commits behind origin while `git pull` reported "Already up to date"). Recommend moving repo out of iCloud Drive on both machines (e.g., `~/code/anti-billionaires-app`) and re-cloning fresh from origin. Until then: every session must start with `git fetch origin && git reset --hard origin/main` (after confirming no uncommitted local work) rather than `git pull`, which can silently lie about freshness.
- ~~**Bryce handoff still pending.**~~ **Resolved 2026-05-02 (manager session):** Kashi confirmed direct ownership of every credential — Railway, Stripe, GHL, domain, email service, repo admin. There is no upstream human dependency to unblock. `BRYCE-HANDOFF.md` is retained as a future-hire reference checklist (the same artifact will apply if a contractor or co-founder is brought in later) but is no longer a launch-gating item. Original blocker text preserved for audit trail in git history (commit before this edit).
- **`GEMINI_API_KEY` exposed via chat 2026-05-02.** Phase 0B executor reported that the Gemini key (Nano Banana / Google Generative AI) was pasted directly in conversation chat to invoke the image-generation skill. Once a key appears in chat it is captured in transcripts/logs we don't control — treat as compromised. **Action: rotate this key immediately** (Google AI Studio → API keys → revoke + reissue). New key goes into `.env.local` (gitignored), executor reads from env, never writes the value back to chat. Add to Bryce-handoff scope so the rotated key is centrally tracked. **Pattern enforcement going forward:** no API keys, webhook secrets, Stripe keys, or session secrets are ever pasted in chat. They live in `.env.local`, in Railway/Vercel env config, or in 1Password. Executors that need a key request it via env var only.
- **Placeholder seed content must be cleaned out OR transparently labeled before any paid launch.** Phase 0B (commit 78f8f47) seeded 8 fictional "Founding Voice" users with bios, posts, wins, deals, resources, RSVPs, and an active weekly challenge. Every placeholder user's bio ends with `— Founding Voice (pre-launch seed account)`, which is honest but visible. Their posts/wins/deals do NOT carry that label — a casual reader of `/feed` would not know they are seed content. **Decision needed before public marketing:** (a) keep the seed content as-is and treat the footer as sufficient disclosure, (b) replace the 8 placeholders with a real founder cohort (Bryce + Kashi's network) before public launch, or (c) run `python seed_placeholders.py --delete` immediately before flipping the marketing switch and operate from an empty community. Cleanup is one command; the choice is content-strategy, not technical. Tracked for Phase 1 of the customer-journey work. Dev login (placeholders only): `seed.<slug>@sovereign.placeholder` / `ChangeBeforeLaunch_2026!`.
- ~~**Production at `https://onepercentmensclub.up.railway.app` is currently NOT serving the app.**~~ **Resolved 2026-05-02 (manager session):** false alarm. The legacy URL was a stale reference in `capacitor.config.json:7` from an older deleted Railway project. The actual live URL is `https://anti-billionaires-app-production.up.railway.app` and has been serving HTTP 200 throughout. `capacitor.config.json` corrected to point at the live URL in same-day commit. The audit's curl probes were aimed at a dead URL because they trusted the stale config — this is the kind of trap that happens when no env-grounded source-of-truth is wired up. New §5 entry mandates that every future audit cross-checks live URL against `railway domain` output, not just static config files. Original blocker text retained for audit trail in git history.
- ~~**`cron.py` weekly digest references nonexistent model fields.** Surfaced 2026-05-02 by Phase 0 audit. `cron.py:64` reads `w.content` on a `Win` (Win has `title` + `description`, no `content`); `cron.py:75-77,82` filter/order by `Event.starts_at` (Event has `date` + `time`, no `starts_at`).~~ (resolved 2026-05-02 by phase-1 — `cron.py:64` now builds `f"{w.title} - {w.description}"` for the digest dict; `cron.py:75-77,82` switched to `Event.date` filter/order with `Event.time` appended to the display string. `flask cron digest` runs to completion when `SERVER_NAME` is set.)
- ~~**GHL tag taxonomy split between legacy `"ABMC"` and new `"Sovereign Society"`.**~~ (resolved 2026-05-02 by phase-1 — single 9-tag canonical taxonomy locked in `lib/ghl.STAGE_TAGS`; brand tags rejected with `ValueError`; all 5 call sites migrated; backfill script `scripts/backfill_ghl_tags.py` shipped — Kashi runs `--apply` separately once Bryce shares live location creds.)
- **`/notifications/read` and `/notifications/mark-read` are duplicate routes** (both POST, both mark-all-read; `app.py:1151` and `app.py:1185`). Not a bug — just dead weight. Pick one, delete the other, retire the duplicate at the next routine cleanup.
- ~~**`cron.py:133` admin-email lookup is buggy.**~~ (resolved 2026-05-02 by phase-1 — `cli_test_email` now does an explicit `if not admin: click.echo("No admin user found - set ADMIN_EMAILS or create one."); return` and uses `click.echo` instead of `print` so `flask cron` plays well with the CLI runner.)
- ~~**Email render fails silently in threaded sends when `_external=True` URLs are used.**~~ (resolved 2026-05-02 by phase-1 — `app.py` now sets `app.config["SERVER_NAME"] = os.environ.get("SERVER_NAME") or ("anti-billionaires-app-production.up.railway.app" if ENV=="production" else None)` and `PREFERRED_URL_SCHEME="https"`. Verified locally that with `SERVER_NAME=localhost:5099 flask cron digest`, the digest renders to completion (HTML + text variants) for 2 active users without `RuntimeError`. Verified that `SERVER_NAME=None` in dev does NOT break: `python app.py` boots, `/feed` and `/api/notifications/unread-count` return HTTP 200 when logged in. Railway env var must be set for production — manager session sets after this phase ships.)
- ~~**`/create-checkout-session` does NOT configure the 30-day Stripe trial. LAUNCH BLOCKER.**~~ **Resolved 2026-05-02 (manager session):** **false alarm.** Phase 1 executor flagged the missing `subscription_data={"trial_period_days": 30}` kwarg in `app.py:1348`, but did not have visibility into the Stripe dashboard. The 30-day trial **IS configured on the Price object itself** (`price_1TSqoGCl2bd6Dz0I44Po79vj` has `recurring.trial_period_days = 30`, verified via Stripe API in same-day manager session). When Stripe Checkout creates a subscription against a Price with a trial, the trial applies automatically — `subscription_data.trial_period_days` is only required to OVERRIDE a price's default. Subscriptions will land in `"trialing"` status as expected; the Phase 0 `has_active_subscription` fix is correctly load-bearing. No code change required. **Pattern note:** future executor sessions probing Stripe state should curl `/v1/prices/<price_id>` (read-only, restricted-key OK) before flagging a "trial not configured" finding — the Stripe-side config can move the goalposts on the local-code-only read. Original blocker text retained for audit trail in git history.
- **Apparel line in scope but not yet scoped.** Per Kashi 2026-05-02: launch a Sovereign Society apparel line (T-shirts, hats, hoodies, "earned merch" pendant for Lifetime-Qualified members) connected to the membership. **Recommended MVP path:** print-on-demand via Printful or Printify, separate Shopify storefront at `shop.sovereignsociety.com` ($39/mo), 4–5 SKUs to launch (logo crewneck tee, manifesto back-print tee, embroidered cap, hoodie, and small-batch manufactured "earned" pendant). Tier integration: 20% member discount via Stripe coupon, Founding-100 numbered tee for first 100 members, Lifetime-Qualified members receive the pendant free. Total upfront: ~$1k–2k for POD launch; manufactured hero piece comes later when revenue justifies. Estimated 5–20 orders week 1, scale tied to Society membership growth. Decisions still needed: which Stripe account (existing membership Stripe or separate Shopify account), apparel designer (freelance vs Nano Banana for patterns + human for typography), launch timing relative to Society public launch. Phase prompt for apparel-line setup TBD — gated on Society launch first OR can run in parallel if Kashi prioritizes.

---

## 11. Update Rules for Future Sessions

1. Read this entire file before doing any work.
2. After completing a task, update §8 (Phase Status) — change ⬜ to ✅, add notes.
3. If you make a decision, append to §9 with date and reason.
4. If you discover a new risk, append to §10.
5. New env vars / pipelines / tags / workflows go into §5, §6 in the same commit.
6. Commit message format: `phase-N: <what changed>` (lowercase). Example: `phase-1: lift ghl client to lib/ghl.py`.
7. Never delete entries from the Decisions Log.

---

## 12. Reference: Customer Journey Playbook

This project will get its own community-flavored playbook in Phase 6. Until then, reference the Stratum playbook structure at `~/stratum-therapeutics/CUSTOMER-JOURNEY-PLAYBOOK.md` and the reusable template at `~/claude-code-playbook/template-customer-journey.md` — same methodology, different content.

---

## 13. Phase 0 Audit Report — 2026-05-02

This appendix captures the read-only discovery output from Phase 0. The two trivial bug fixes shipped in commit `1116d92`. This audit ships in its own commit so code-changes and doc-changes have separate blame.

### 13.1 Routes Inventory (complete)

**`app.py` — 54 routes**

| Method | Path | Handler |
|--------|------|---------|
| GET | `/` | `index` |
| POST | `/api/devices/register` | `register_device` |
| POST | `/api/devices/unregister` | `unregister_device` |
| GET, POST | `/preferences/digest` | `toggle_digest` |
| GET | `/terms` | `terms` |
| GET | `/privacy` | `privacy` |
| GET | `/onboarding` | `onboarding` |
| POST | `/onboarding` | `onboarding_submit` |
| GET | `/feed` | `feed` |
| POST | `/feed` | `create_post` |
| POST | `/like/<int:post_id>` | `toggle_like` |
| POST | `/comment/<int:post_id>` | `add_comment` |
| DELETE | `/post/<int:post_id>` | `delete_post` |
| GET, POST | `/login` | `login` |
| GET, POST | `/signup` | `signup` |
| GET | `/logout` | `logout` |
| GET, POST | `/forgot-password` | `forgot_password` |
| GET, POST | `/reset-password/<token>` | `reset_password` |
| GET | `/verify-email/<token>` | `verify_email` |
| POST | `/resend-verification` | `resend_verification` |
| GET | `/profile/<int:user_id>` | `profile` |
| GET, POST | `/profile/edit` | `edit_profile` |
| GET | `/members` | `members` |
| GET | `/leaderboard` | `leaderboard` |
| POST | `/follow/<int:user_id>` | `toggle_follow` |
| GET | `/spaces` | `spaces` |
| GET | `/space/<int:space_id>` | `space_detail` |
| GET, POST | `/space/create` | `create_space` |
| POST | `/space/<int:space_id>/join` | `join_space` |
| POST | `/space/<int:space_id>/leave` | `leave_space` |
| POST | `/space/<int:space_id>/post` | `create_space_post` |
| GET | `/notifications` | `notifications` |
| POST | `/notifications/read` | `mark_notifications_read` |
| GET | `/api/notifications/unread-count` | `api_unread_count` |
| GET | `/api/notifications/recent` | `api_recent_notifications` |
| POST | `/notifications/mark-read` | `mark_read` *(duplicate of `/notifications/read`)* |
| POST | `/poll/vote/<int:option_id>` | `vote_poll` |
| GET | `/pricing` | `pricing` |
| POST | `/validate-code` | `validate_code` |
| POST | `/create-checkout-session` | `create_checkout_session` |
| GET, POST | `/subscription/success` | `subscription_success` |
| POST | `/webhook/stripe` | `stripe_webhook` *(CSRF-exempt)* |
| POST | `/billing-portal` | `billing_portal` |
| GET | `/admin` | `admin_panel` |
| GET | `/admin/member/<int:user_id>` | `admin_member_detail` |
| POST | `/admin/toggle-admin/<int:user_id>` | `toggle_admin` |
| POST | `/admin/toggle-subscription/<int:user_id>` | `toggle_subscription` |
| POST | `/admin/grant-lifetime/<int:user_id>` | `admin_grant_lifetime` |
| POST | `/admin/revoke-lifetime/<int:user_id>` | `admin_revoke_lifetime` |
| POST | `/admin/refund-last/<int:user_id>` | `admin_refund_last` |
| POST | `/admin/comp-month/<int:user_id>` | `admin_comp_month` |
| GET | `/learn` | `learn` *(redirect → phase3.lessons)* |

**`phase3_routes.py` — 9 routes (blueprint `phase3`)**

| Method | Path | Handler |
|--------|------|---------|
| GET | `/events` | `events` |
| GET | `/events/<int:event_id>` | `event_detail` |
| GET, POST | `/events/create` | `create_event` *(admin-only)* |
| POST | `/events/<int:event_id>/rsvp` | `event_rsvp` |
| GET | `/lessons` | `lessons` |
| GET | `/lessons/<int:course_id>/<int:lesson_id>` | `lesson_detail` |
| POST | `/lessons/<int:course_id>/<int:lesson_id>/complete` | `complete_lesson` |
| GET | `/welcome` | `welcome` *(checklist)* |
| POST | `/welcome/check/<int:item_id>` | `check_item` |

**`features_routes.py` — 42 routes (blueprint `features`)**

| Method | Path | Handler |
|--------|------|---------|
| GET | `/messages` | `inbox` |
| GET | `/messages/new/<int:user_id>` | `new_conversation` |
| GET | `/messages/<int:convo_id>` | `chat` |
| POST | `/messages/<int:convo_id>/send` | `send_message` |
| GET | `/messages/<int:convo_id>/poll` | `poll_messages` |
| GET | `/api/messages/unread-count` | `api_unread_messages` |
| POST | `/stories/create` | `create_story` |
| GET | `/stories/<int:story_id>` | `view_story` |
| GET | `/api/stories` | `api_stories` |
| GET | `/wins` | `wins` |
| POST | `/wins/create` | `create_win` |
| POST | `/wins/<int:win_id>/react` | `react_win` |
| GET | `/deals` | `deals` |
| GET, POST | `/deals/create` | `create_deal` |
| GET | `/deals/<int:deal_id>` | `deal_detail` |
| POST | `/deals/<int:deal_id>/interest` | `deal_interest` |
| GET | `/challenges` | `challenges` |
| GET, POST | `/challenges/create` | `create_challenge` *(admin-only)* |
| GET | `/challenges/<int:ch_id>` | `challenge_detail` |
| POST | `/challenges/<int:ch_id>/submit` | `submit_challenge` |
| POST | `/challenges/submission/<int:sub_id>/vote` | `vote_submission` |
| GET | `/resources` | `resources` |
| GET, POST | `/resources/create` | `create_resource` |
| POST | `/resources/<int:res_id>/upvote` | `upvote_resource` |
| GET | `/referrals` | `referrals` |
| GET | `/r/<code>` | `referral_landing` *(public)* |
| GET | `/accountability` | `accountability` |
| POST | `/accountability/pair/<int:user_id>` | `create_pair` |
| POST | `/accountability/goals/create` | `create_goal` |
| POST | `/accountability/goals/<int:goal_id>/checkin` | `goal_checkin` |
| POST | `/accountability/goals/<int:goal_id>/complete` | `complete_goal` |
| GET | `/bookmarks` | `bookmarks` |
| POST | `/bookmark/<int:post_id>` | `toggle_bookmark` |
| GET | `/badges` | `badges_page` |
| GET | `/reels` | `reels` |
| GET, POST | `/reels/create` | `create_reel` |
| GET | `/space/<int:space_id>/chat` | `space_chat` |
| POST | `/space/<int:space_id>/chat/send` | `send_space_chat` |
| GET | `/space/<int:space_id>/chat/poll` | `poll_space_chat` |
| GET | `/wingman` | `wingman` |
| POST | `/wingman/send` | `wingman_send` |
| GET | `/map` | `member_map` |
| POST | `/profile/location` | `update_location` |
| GET | `/book/<int:user_id>` | `booking_page` |
| POST | `/book/<int:user_id>/create` | `create_booking` |
| GET | `/bookings` | `my_bookings` |
| POST | `/bookings/<int:booking_id>/confirm` | `confirm_booking` |
| POST | `/bookings/<int:booking_id>/cancel` | `cancel_booking` |
| GET | `/boardroom` | `boardroom` *(Platinum or Level 9+)* |
| GET | `/spotlights` | `spotlights` |
| GET | `/activity` | `activity_feed` |
| GET | `/search` | `search` |

(Counts: app.py 54 + phase3 9 + features 42 = 105 unique route definitions.)

### 13.2 Stripe State

- **Mode (local):** `STRIPE_SECRET_KEY` is UNSET in this dev shell → `app.py:82` falls back to literal `"sk_test_placeholder"`. `app.py:1242` short-circuits checkout when the key is placeholder. Cannot determine production mode without Railway dashboard access.
- **`STRIPE_PRICE_ID`:** UNSET locally; default `"price_placeholder"`. Validity in production needs manual verification by Kashi (Stripe CLI not installed locally; no `stripe prices retrieve` available).
- **Webhook route:** `POST /webhook/stripe` (`app.py:1361`), CSRF-exempt, signature-verified via `stripe.Webhook.construct_event` against `STRIPE_WEBHOOK_SECRET`. Idempotent via `StripeEvent` table on `stripe_event_id`.
- **Webhook events handled:**
  - `checkout.session.completed` → `_handle_checkout_completed` (backfills `stripe_customer_id` if user already exists by email)
  - `customer.subscription.updated` → `_handle_subscription_updated` (refreshes `subscription_status` + `current_period_end`; skips if user is `lifetime_access`)
  - `customer.subscription.deleted` → `_handle_subscription_deleted` (sets status `canceled`, **calls `ghl_upsert_contact(...tags=["Churned", "ABMC"])`**)
  - `invoice.payment_succeeded` → `_handle_payment_succeeded` (increments `payments_made_count`; at 6, increments referrer's `qualified_referrals_count`; at 3, flips referrer to `lifetime_access=True`, cancels referrer's Stripe sub, calls `ghl_upsert_contact(...tags=["Lifetime", "ABMC"])` and `send_lifetime_unlocked` email)
  - `invoice.payment_failed` → `_handle_payment_failed` (sets status `past_due`, sends `send_payment_failed` email)
- **Webhook → GHL:** YES on `subscription.deleted` (Churned tag) and `payment_succeeded → lifetime branch` (Lifetime tag). NO on the other 3 events. (Phase 2 widens this.)

### 13.3 GHL State

- `ghl_upsert_contact()` shape and call sites: see updated §6.
- `GHL_API_KEY`: UNSET locally. `GHL_LOCATION_ID`: UNSET locally.
- No live ping attempted (env unset → no auth).

### 13.4 Deploy State

- **Builder:** Railway with NIXPACKS (`railway.json`), Python provider (`nixpacks.toml`).
- **Procfile:** `web: gunicorn app:app -w 4 --threads 2 --worker-class gthread --timeout 60`.
- **Start command (production):** `flask db upgrade && gunicorn app:app -w 4 --threads 2 --worker-class gthread --timeout 60` (from `railway.json`). Migrations run automatically before gunicorn starts. Restart policy: `ON_FAILURE` × 10.
- **Live URL:** `https://onepercentmensclub.up.railway.app` (declared in `capacitor.config.json:7`). `curl -I` returns HTTP 404 with `x-railway-fallback: true` on `/`, `/pricing`, `/healthz` → **production is currently down or service is unbound**. See §10.
- **Last code deploy:** Most recent commit on `origin/main` is `02d87f1` (sot: log gemini api key exposure + rotation pattern). Railway auto-deploys from main, so it should have run, but the live URL is not serving — disconnect between repo and runtime.
- **Migrations:** 7 alembic revisions in `migrations/versions/`:
  1. `43be3a8d6b40_initial_schema_baseline`
  2. `88a0045f8905_auth_hardening_lifetime_access_fields`
  3. `9c1f2a3e4d5b_stripe_event_idempotency_log`
  4. `abcd1234e5f6_engagement_email_throttling`
  5. `c2d3e4f5a6b7_perf_indexes` (23 hot-path indexes)
  6. `d3e4f5a6b7c8_device_tokens`
  7. `e4f5a6b7c8d9_referral_qualification_fields`
- **`_seed_content()` trigger:** `app.py:399-405` runs at module import time inside `with app.app_context()`, wrapped in try/except. Gunicorn forks 4 workers; this will run 4 times, but `_seed_content()` is idempotent (existence checks before insert). Side effect: brief startup log noise. Fine for MVP.
- **`seed_checklist()` and `seed_badges()`** also run at startup (`app.py:271-278`) — also idempotent.

### 13.5 Email Infrastructure

- **Service:** Resend (`resend==2.0.0` in `requirements.txt`; `email_send.py:18-29`).
- **Sender:** `EMAIL_FROM` defaults to `onboarding@resend.dev` (Resend's shared sandbox domain — works for testing but will land in spam at scale and signals "not a real product"). `EMAIL_FROM_NAME` defaults to `Sovereign Society`.
- **Production sender domain (TBD):** No custom sender domain configured today. Needs DKIM/SPF/DMARC at the registrar of whatever domain Sovereign Society lands on — likely `sovereignsociety.com` per Phase 0A intent. Also tied to the stale `support@onepercentmensclub.com` cleanup in §10.
- **Fallback:** when `RESEND_API_KEY` is unset, `_send_now` prints to stdout (console stub) — dev-friendly, won't crash.
- **Templates (`templates/emails/`):** `_layout.html`, `welcome_verify`, `password_reset`, `payment_succeeded`, `payment_failed`, `referral_qualified`, `lifetime_unlocked`, `weekly_digest` — each with `.html` + `.txt` pair (15 files total + 1 layout).
- **Typed senders (`email_send.py`):** `send_welcome_verify`, `send_password_reset`, `send_payment_succeeded`, `send_referral_progress`, `send_payment_failed`, `send_lifetime_unlocked`, `send_weekly_digest`, plus the generic `send_email`.
- **Engagement throttling (`cron.py`):** `notify_dm_throttled` enforces 1 DM-email per recipient per hour via `User.last_engagement_email_at`. Weekly digest enforces 6-day idempotency via `User.last_digest_sent_at`. Both honor `email_digest_opt_out`. Unsubscribe link → `/preferences/digest`.

### 13.6 Database State

- **`DATABASE_URL`:** UNSET locally → `app.py:49` falls back to `sqlite:///abmc.db`. `app.py:50-51` rewrites `postgres://` → `postgresql://` (Railway gives the bare prefix; SQLAlchemy 1.4+ wants the explicit driver).
- **Local instance dir:** `/instance/` does not exist on this machine — fresh checkout, no SQLite has been created here. Not a problem (will create on first `python app.py` run).
- **Engine pool config (Postgres only):** `pool_pre_ping=True`, `pool_size=5`, `max_overflow=10`, `pool_recycle=1800` — sane defaults for Railway's connection limits.
- **Migration count:** 7 (see §13.4).
- **Indexes:** the `c2d3e4f5a6b7_perf_indexes` migration creates 23 indexes covering hot read paths: post (user_id, space_id, created_at), comment (post_id), like (post_id, user_id), notification (user_id, is_read), conversation (user1, user2), message (conversation_id, is_read), win (created_at), space_membership (user_id, space_id), user (subscription_status, lifetime_access), ai_chat (user_id, created_at), activity (user_id), bookmark (user_id), follow (follower_id, followed_id). Also explicit indexes on `User.email_verify_token` and `User.password_reset_token` (in the model definition).
- **Indexes worth flagging for production load (not changing now):** no index on `User.email` (it's the `unique=True` column so it gets one implicitly — fine), no index on `User.referred_by` (referral lookups will table-scan once `User.count()` grows past a few thousand — Phase 1 should add).

### 13.7 Other surprises / launch-blocker candidates

- **Production is currently 404.** Already in §10 — repeated here because it surfaced during this audit and is the single most important thing to resolve before any Phase 1 work. Until the Railway service is bound + healthy, every other phase is blocked from production verification.
- **`cron.py:64,75-77,82` field bugs.** Already in §10. Weekly digest will crash on first run.
- **`cron.py:133` admin-email lookup bug.** Already in §10. Test-email CLI will crash if no admin user exists.
- **GHL tag taxonomy split.** Already in §10. Workflows that filter on `"ABMC"` will miss paid signups; workflows filtering on `"Sovereign Society"` will miss everything else.
- **`/notifications/read` and `/notifications/mark-read` duplicate routes.** Already in §10.
- **Capacitor bundle ID + server URL still legacy.** `appId: com.onepercentmensclub.app`, `server.url: https://onepercentmensclub.up.railway.app`, `ios.scheme: OnePercentMC`. Per CLAUDE.md these are infrastructure-tied and intentionally NOT renamed (Apple/Google review process pain). Document only — no action.
- **PWA manifest is minimal but valid.** `static/manifest.json` declares Sovereign Society branding, dark theme color, two icon sizes. Acceptable for v1.
- **No TODO/FIXME/XXX markers** anywhere in `app.py`, `phase3_routes.py`, `features_routes.py`, `email_send.py`, `models.py`, or `cron.py`. Either the codebase is genuinely clean of inline cruft, or such markers were never used as a convention.
- **No `lib/` directory yet.** GHL client lifting (Phase 1 scope) will create it.
- **No tests currently run as part of the deploy.** `pytest` and `pytest-flask` are in `requirements.txt` but no `tests/` directory exists, no CI workflow file (`.github/workflows/`) was found in the read-mandated paths. Deploy validation is purely manual today. Acceptable for MVP, but flag once paid signups happen.
