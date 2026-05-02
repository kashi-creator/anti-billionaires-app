# Bryce Handoff — Sovereign Society Credentials & Access Checklist

> Send this to Bryce. Ask him to reply with: (1) which items he holds today, (2) which need to be created, (3) confirmation Kashi has primary or co-owner status on every account, (4) 2FA recovery codes, (5) a single Notion page or 1Password vault with everything centralized.
>
> Last updated: 2026-05-02

---

## TL;DR for Bryce

We're moving Sovereign Society from "I'm helping Kashi build it" to "Kashi owns and operates it." Every credential, account admin, and DNS record below needs to be verifiably under Kashi's control before public launch. If you're a co-founder, this means co-ownership. If you're a contractor, this means full transfer.

This is non-negotiable for launch. If you get hit by a bus, the business has to keep running.

---

## 1. Critical (cannot launch without these)

### Stripe (production / live mode)

- [ ] `STRIPE_SECRET_KEY` (`sk_live_...`)
- [ ] `STRIPE_PUBLISHABLE_KEY` (`pk_live_...`)
- [ ] `STRIPE_WEBHOOK_SECRET` (`whsec_...`)
- [ ] `STRIPE_PRICE_ID` for the **$99/month product with `trial_period_days = 30`** configured
- [ ] Confirmation Stripe is in **LIVE mode**, not test mode
- [ ] Stripe Dashboard admin access transferred or co-shared with Kashi (`kashi@thebreathcoachschool.com` for now — will move to a Sovereign Society email once domain is locked)
- [ ] Confirmation that the webhook endpoint is registered and receives `customer.subscription.created`, `updated`, `deleted`, `trial_will_end`, `invoice.payment_succeeded`, `invoice.payment_failed`

### GHL (Go High Level)

- [ ] `GHL_API_KEY` — must be tied to the **Sovereign Society GHL location**, NOT shared with Stratum or any other business
- [ ] `GHL_LOCATION_ID`
- [ ] GHL admin access for Kashi on this specific location
- [ ] Confirmation: this is a fresh location with no contaminated contact data from "Anti Billionaires" / "1% Men's Club" / Stratum

### Domain + DNS

- [ ] Domain registrar login (Namecheap / GoDaddy / wherever) for the chosen domain (likely `sovereignsociety.com` — confirm with Kashi)
- [ ] DNS provider access (Cloudflare / Route 53 / etc.) — needed for: email DKIM/SPF/DMARC, subdomain routing (`shop.`, `app.`, `mail.`), future apparel store
- [ ] Any other domains owned that are SS-related (old brand domains: `onepercentmensclub.com`, `antibillionaires.com`?) — list them all and confirm renewals are on autopay under an account Kashi can access

### Email sending

- [ ] Email service API key (Resend / Mailgun / Postmark / SendGrid — Phase 0 audit will confirm which)
- [ ] Sender domain ownership confirmation
- [ ] DKIM, SPF, DMARC DNS records configured for the sender domain (or confirm they need to be added)
- [ ] If currently using `@onepercentmensclub.com` or any legacy address — list every place that's hardcoded so we can swap

### Railway (hosting)

- [ ] Railway project admin access for Kashi
- [ ] Project name + service name
- [ ] Confirmation of which env vars are currently set in production (full list, names only)
- [ ] Railway billing — whose card is it on?

### GitHub

- [ ] Admin access to `kashi-creator/anti-billionaires-app`
- [ ] List of all collaborators / their permission levels
- [ ] Note: there's a known issue — a GitHub PAT may be exposed in the git remote URL on one of the local clones. Bryce, please confirm what tokens you've issued for this repo so we can rotate them.

### Production secrets

- [ ] `SECRET_KEY` (Flask session signing key) — what's the production value? Don't rotate it without coordinating; rotation invalidates every active session.
- [ ] `ADMIN_EMAILS` env var — what's currently set? At minimum we need 2 admin humans listed.

---

## 2. Soon (within 30 days post-launch)

### Email infra (additional)

- [ ] Anthropic API key (for the AI Wingman feature — currently a placeholder in code)
- [ ] Backup sender domain or service in case the primary gets flagged for spam during a paid-traffic launch

### Mobile app (if shipping iOS / Android — currently scoped via Capacitor)

- [ ] Apple Developer account ($99/yr) — admin access for Kashi
- [ ] App Store Connect access
- [ ] Current Capacitor bundle ID is `com.onepercentmensclub.app` (legacy from the 1% Men's Club name) — decision needed: rename to `com.sovereignsociety.app` or keep legacy. Renaming requires App Store re-submission.
- [ ] APNs (Apple Push Notification) auth key — the `.p8` file + key ID + team ID
- [ ] If shipping Android: Google Play Console admin access + FCM (Firebase) project credentials

### Analytics + ad infra

- [ ] Google Analytics property (or Plausible / Fathom — privacy-aware alternatives that fit the brand better)
- [ ] Meta Pixel + Facebook Business Manager admin (for paid ads on Meta properties)
- [ ] TikTok Business / Pixel (depending on creator-strategy choice)
- [ ] X (Twitter) account handle for the brand + login + 2FA recovery
- [ ] Instagram handle + login + 2FA recovery

### File storage (launch blocker for any uploads at scale)

- [ ] AWS S3 bucket OR Cloudflare R2 bucket — credentials, region, bucket name. **`static/uploads/` currently writes to Railway disk which is ephemeral on every deploy — uploads vanish.** Must migrate before any real member uploads matter.

---

## 3. Eventually (post-launch, scaling)

- [ ] Cloudflare WAF / DDoS protection (set up once we have meaningful traffic)
- [ ] Sentry (or alternative) for error tracking
- [ ] Status-page subscription on email provider (so we know when delivery is degraded)
- [ ] Old social handles: `@AntiBillionaires`, `@1PercentMensClub`, etc. — reclaim, redirect, or formally retire
- [ ] Trademark search on "Sovereign Society" via USPTO before scaling marketing spend (and possibly file)
- [ ] Business entity confirmation — what LLC / corp owns Sovereign Society? Who are the members of the LLC? Is the EIN tied to a Stripe Tax / Stripe Atlas profile correctly? (If unsure, this becomes a separate accountant + lawyer task.)

---

## What I (Kashi) need from Bryce by the end of this week

1. **Reply** to every checkbox above with: HAVE / NEED / NOT SURE.
2. **A consolidated handoff doc** — Notion page OR 1Password vault — containing every credential, every account login, every API key, every recovery method. One source of truth.
3. **2FA recovery codes** for any account where you're the only 2FA device.
4. **Confirmation** that within 14 days, Kashi will be added as primary or co-owner on every account that touches Sovereign Society.

If any of this is uncomfortable — talk to me directly, don't ghost the doc. The goal isn't to push you out, the goal is durability. If Sovereign Society scales, we both want it to scale on rails that don't depend on any single person being reachable.

---
