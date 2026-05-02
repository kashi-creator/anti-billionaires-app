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
| 0 — Current state audit | ⬜ pending | Verify routes, envs, GHL existing wiring, Stripe state, deploy state |
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

---

## 10. Known Risks / Open Questions

- **GitHub PAT exposed in git remote URL** (verified earlier) — needs rotation
- **Inline GHL function in app.py** — refactor to `lib/ghl.py` in Phase 1 for testability
- **No Celery** — background tasks use threading. Fine for MVP, watch for race conditions
- **File uploads stored on Railway disk** — Railway disks are ephemeral on deploys; migrate to S3/R2 before launch
- **Stripe subscription cancellation handling** — needs verification (does the app actually downgrade access on cancel?)
- **`User.has_active_subscription` rejects `"trialing"` status** ([models.py:120-126](models.py#L120-L126)) — current code only treats `"active"` as active. With the locked 30-day-trial model, every trial user will be paywalled out the moment they sign up. **Launch blocker.** Phase 0 fixes this — change to `self.subscription_status in ("active", "trialing")`.
- **Multiple Stripe price IDs?** — one tier today (`STRIPE_PRICE_ID`) — might need annual + monthly + founder pricing
- **GHL location separate from Stratum's** — must NOT cross-contaminate contact data between businesses
- **Repo lives in iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/Desktop/anti-billionaires-app`).** iCloud syncs both the working tree AND the `.git` folder, which causes ref drift between machines (observed 2026-05-02: local `main` was 10 commits behind origin while `git pull` reported "Already up to date"). Recommend moving repo out of iCloud Drive on both machines (e.g., `~/code/anti-billionaires-app`) and re-cloning fresh from origin. Until then: every session must start with `git fetch origin && git reset --hard origin/main` (after confirming no uncommitted local work) rather than `git pull`, which can silently lie about freshness.

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
