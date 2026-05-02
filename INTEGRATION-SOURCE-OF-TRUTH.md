# Sovereign Society (anti-billionaires-app) — Integration Source of Truth

> **Master reference for any Claude Code session that touches this project.**
> Every session reads this file first. Every session updates the relevant section before exiting. Do not skip — the next session depends on it.

---

## 1. Project Identity

- **Brand name:** Sovereign Society (formerly "The 1% Men's Club" / "Anti Billionaires")
- **Repo:** github.com/kashi-creator/anti-billionaires-app
- **Local repo (laptop):** `~/Desktop/anti-billionaires-app`
- **Local repo (Mac mini):** [TBD — clone path]
- **Hosted:** Railway (project name TBD — Phase 0 confirms)
- **Live URL:** [TBD — Phase 0 fills]
- **Custom domain:** [TBD]
- **GHL location ID:** [TBD — Phase 1 fills, separate from Stratum's location]
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

## 4. Routes Inventory (current state — Phase 0 should verify completeness)

Auth: `/login`, `/signup`, `/logout`, `/reset-pwd/<secret>`
Feed: `/`, `/feed`, `/like/<id>`, `/comment/<id>`, `/post/<id>`
Profile: `/profile/<id>`, `/profile/edit`, `/members`, `/leaderboard`, `/follow/<id>`
Spaces: `/spaces`, `/space/<id>`, `/space/create`, `/space/<id>/join`, `/space/<id>/leave`, `/space/<id>/post`
Notifications: `/notifications`, `/notifications/read`, `/api/notifications/unread-count`, `/api/notifications/recent`
Polls: `/poll/vote/<id>`
Subscriptions: `/pricing`, `/validate-code`, `/create-checkout-session`
Plus routes from `phase3_routes.py` and `features_routes.py` (Phase 0 lists these)

---

## 5. Environment Variables

### Currently expected by `app.py`
- `SECRET_KEY` (Flask session secret)
- `DATABASE_URL` (Postgres on Railway, sqlite fallback in dev)
- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID` (the subscription price)
- `GHL_API_KEY`
- `GHL_LOCATION_ID`

### Phase 0 verifies
Run `railway variables` on this project's service to list what is actually set.

### Likely needed in later phases
- `GHL_MEMBER_PIPELINE_ID`
- `GHL_PROSPECT_PIPELINE_ID`
- `GHL_ONBOARDING_WORKFLOW_ID`
- `GHL_CANCELLATION_WORKFLOW_ID`

---

## 6. GHL Integration — Current State

**There is already a `ghl_upsert_contact()` function in `app.py` (line ~111).** It POSTs to GHL with email, name, tags, phone. It is called at minimum on Founder signup with tags `["Founder", "ABMC"]` (line ~558).

This means partial integration EXISTS. Phase 1 audits it.

### What's likely missing
- Stripe webhook handler does not push to GHL (verify in Phase 2)
- Engagement events (post created, course completed, win posted) do not tag GHL
- Cancellation does not flag GHL for win-back
- No workflow triggers connected to specific tags
- No pipelines defined yet for member lifecycle stages
- API client is inline in `app.py` — should be lifted to `lib/ghl.py` for reuse

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
| 0 — Current state audit | ⬜ pending | Verify routes, envs, GHL existing wiring, Stripe state, deploy state. Includes 2 trivial bug fixes (port 5000 hardcode, `has_active_subscription` trial). Prompt at `phase-prompts/phase-0-audit.md` — runs in parallel with 0B |
| 0A — Public copy + Terms alignment with locked business model | ✅ done | Rewrite landing.html FAQ #2/#5/#6, fix pricing.html ($100 → $99, add trial + lifetime mechanic), rewrite legal.html Terms §2 with proper subscription disclosure. Prompt at `phase-prompts/phase-0a-copy-terms-alignment.md` — completed 2026-05-02, commit e4aa7fc |
| 0B — Seed empty community with placeholder content + imagery | ⬜ pending | Create 8 placeholder "Founding Voice" users + ~16 posts + 4 wins + 4 deals + 7 resources + 1 challenge + 3 events; generate 11 abstract gold-on-black images via Nano Banana; idempotent re-run + `--delete` cleanup. Prompt at `phase-prompts/phase-0b-content-seeding.md` |
| 1 — Lift GHL into proper client + tighten existing integration | ⬜ pending | Move inline `ghl_upsert_contact` to `lib/ghl.py`, add helpers, add custom fields + tag taxonomy, define pipelines |
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
- **2026-05-02 — Phase 0A complete (commit e4aa7fc).** Public copy + Terms reconciled with locked business model. Three files edited: `templates/landing.html` (FAQ #2/#5/#6 rewritten), `templates/pricing.html` ($100→$99, +trial banner under tagline, +lifetime referral note under cancel-anytime), `templates/legal.html` (§2 expanded into Membership & Billing, new §2A Lifetime Access — Referral-Earned). Repo-wide grep for residual stale copy (`99/month for|three months|three payments|3 payments|3 months`) returned clean. Verified live on local Flask (port 5050; macOS Control Center holds 5000) — `/`, `/pricing`, `/terms` all 200; section ordering reads 1, 2, 2A, 3, 4, 5, 6, 7, 8 as specified. **Final FAQ #2 wording (canonical, quote verbatim in future copy):** "$99 / month, ongoing. Your first 30 days are free — you sign up with a card on file but no charge hits until day 31. There is no fixed end to the membership; you can cancel any time. The Society also offers Lifetime Access — but you don't buy it, you earn it. Bring three brothers into the Society. Once each one has completed six paid months ($594 each), your billing ends permanently and your seat is yours for life." **Final Terms §2A wording (canonical, contract-law load-bearing):** "Sovereign Society offers Lifetime Access at no further charge to members who successfully refer at least three (3) other paying members, where each of those three referrals must independently complete six (6) consecutive months of $99 payments — a total of $594 paid by each referral, or $1,782 in total referral-driven revenue, before the referring member qualifies. Once you reach this threshold, your $99 monthly billing will be permanently terminated and your platform access becomes Lifetime, contingent on continued adherence to the Member Code of Conduct (Section 4). The following do NOT count toward referral qualification: trial-period months (no payment was made); refunded payments; charged-back payments; payments made by referrals who later cancelled before reaching six successful payments. If a referral cancels before completing six payments, their progress does not transfer and is not bankable for a future re-signup. There is no other path to Lifetime Access. Statements elsewhere on the website that may have suggested an alternative path are superseded by this Section."

---

## 10. Known Risks / Open Questions

- **GitHub PAT exposed in git remote URL** (verified earlier) — needs rotation
- **Inline GHL function in app.py** — refactor to `lib/ghl.py` in Phase 1 for testability
- **No Celery** — background tasks use threading. Fine for MVP, watch for race conditions
- **File uploads stored on Railway disk** — Railway disks are ephemeral on deploys; migrate to S3/R2 before launch
- **Stripe subscription cancellation handling** — needs verification (does the app actually downgrade access on cancel?)
- **`User.has_active_subscription` rejects `"trialing"` status** ([models.py:120-126](models.py#L120-L126)) — current code only treats `"active"` as active. With the locked 30-day-trial model, every trial user will be paywalled out the moment they sign up. **Launch blocker.** Phase 0 fixes this — change to `self.subscription_status in ("active", "trialing")`.
- ~~**Public copy misrepresents the offer.** `templates/landing.html` (FAQ), `templates/pricing.html` ($100 typo + missing trial/lifetime), and `templates/legal.html` (Terms §2) all promise "$99/month for 3 months → lifetime" — a model the code does not implement and which Kashi has confirmed is NOT the actual offer. **Material contract-law exposure if signups happen against this text.** Launch blocker. Phase 0A reconciles all three files.~~ (resolved 2026-05-02 by phase-0a, commit e4aa7fc)
- **Stale support email `support@onepercentmensclub.com`** in `legal.html` (Terms §8 + Privacy §"Your Rights"). Old brand. Need new support email on `sovereignsociety.com` or another chosen domain — depends on Q7 (email sender domain). Cleanup once domain locked.
- **Port 5000 hardcoded in `app.py:1709`.** Surfaced 2026-05-02 by Phase 0A executor — macOS Control Center holds port 5000, blocking local dev. Fix: change `app.run(port=5000)` to `app.run(port=int(os.getenv("PORT", 5000)))`. Trivial 1-line fix, fold into Phase 0 audit.
- **`legal.html` Terms §4 (Member Code of Conduct) is still placeholder text** ("Members agree to engage respectfully…"). The new §2A invokes it as a contingency for Lifetime Access continuation, so when §2A goes live, §4 needs real, enforceable conduct rules. Phase 7 (Compliance + community guidelines) work.
- **`legal.html` `Last updated: April 2026` date is stale** (actual content was updated 2026-05-02 by Phase 0A). Needs a refresh, plus a forward decision on whether to track legal-page revision history (changelog at top of file, archived versions, etc.). Cleanup before any paid signup.
- **Multiple Stripe price IDs?** — one tier today (`STRIPE_PRICE_ID`) — might need annual + monthly + founder pricing
- **GHL location separate from Stratum's** — must NOT cross-contaminate contact data between businesses
- **Repo lives in iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/Desktop/anti-billionaires-app`).** iCloud syncs both the working tree AND the `.git` folder, which causes ref drift between machines (observed 2026-05-02: local `main` was 10 commits behind origin while `git pull` reported "Already up to date"). Recommend moving repo out of iCloud Drive on both machines (e.g., `~/code/anti-billionaires-app`) and re-cloning fresh from origin. Until then: every session must start with `git fetch origin && git reset --hard origin/main` (after confirming no uncommitted local work) rather than `git pull`, which can silently lie about freshness.
- **Bryce handoff still pending.** Production credentials (Stripe, GHL, Railway, domain, email service API keys, repo admin) are currently held by Bryce. Full transfer / co-ownership checklist drafted at `BRYCE-HANDOFF.md` (to be sent to Bryce). Until every checkbox there is confirmed, Sovereign Society depends on a single non-Kashi human to keep running — durability risk and launch blocker for anything beyond local dev. Critical items for any production launch: Stripe keys (`sk_live_*`, webhook secret, price ID with `trial_period_days=30`), GHL API key + location ID (must be a fresh location, NOT shared with Stratum), Railway admin access, domain registrar + DNS access, email-service API key.
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
