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
| 1 — Prospect | `prospect` | Signed up free / browsing pricing | Email nurture |
| 2 — Trial / Signup-no-pay | `signup` | Account created, no subscription | Activation push |
| 3 — Active Member | `active-member` + tier-specific | Paying subscriber | Engagement loops |
| 4 — Power Member | `power-member` | High activity (posts, course completion, events) | VIP perks, referral push |
| 5 — At-Risk | `at-risk` | Low activity 21+ days | Re-engagement |
| 6 — Cancelled | `cancelled` | Subscription ended | Win-back sequence |
| 7 — Reactivated | `reactivated` | Came back after cancel | Re-onboarding |

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

- _(empty — first session adds entries here)_

---

## 10. Known Risks / Open Questions

- **GitHub PAT exposed in git remote URL** (verified earlier) — needs rotation
- **Inline GHL function in app.py** — refactor to `lib/ghl.py` in Phase 1 for testability
- **No Celery** — background tasks use threading. Fine for MVP, watch for race conditions
- **File uploads stored on Railway disk** — Railway disks are ephemeral on deploys; migrate to S3/R2 before launch
- **Stripe subscription cancellation handling** — needs verification (does the app actually downgrade access on cancel?)
- **Multiple Stripe price IDs?** — one tier today (`STRIPE_PRICE_ID`) — might need annual + monthly + founder pricing
- **GHL location separate from Stratum's** — must NOT cross-contaminate contact data between businesses

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
