# Phase 0A — Reconcile Public Copy + Terms with Locked Business Model

> Paste this entire prompt into a fresh Claude Code session opened in `~/Desktop/anti-billionaires-app` (or wherever the local clone lives). Do not modify the prompt; the manager session sized the scope deliberately.

---

## Step 0 — Pull before reading

```bash
git fetch origin && git status
```

If `main` is behind origin: `git reset --hard origin/main` (after confirming no uncommitted local work). The repo lives in iCloud Drive on at least one machine, which causes ref drift; do not trust `git pull` alone.

---

## Step 1 — Read first (mandatory)

Read these files in full:

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — read everything, especially §7 (Customer Journey), §9 (Decisions Log entries from 2026-05-02), §10 (Known Risks).
2. `templates/landing.html` — the canonical brand voice + the wrong FAQ that must be rewritten (FAQ items #2, #5, #6).
3. `templates/pricing.html` — has a $100 typo (locked price is $99), missing 30-day trial language, missing the lifetime referral mechanic entirely.
4. `templates/legal.html` — has a `body_template == 'legal_terms'` branch with Section 2 (Membership) that misrepresents the offer.
5. `models.py` lines 60–70 — confirm the referral/lifetime fields and their docstrings (do NOT modify the model).
6. `app.py` — find the `/terms`, `/pricing`, `/create-checkout-session` route handlers so you understand the page-flow context (do NOT modify business logic in this phase).

---

## Step 2 — The locked business model (DO NOT change these facts)

1. **Price:** $99/month, ongoing, no fixed end. (NOT $100, NOT "3 payments then done.")
2. **Trial:** 30 days free. Card required at signup. Stripe `subscription_data.trial_period_days = 30`. Auto-bills on day 31.
3. **Lifetime access:** Earned ONLY via referrals. A member earns lifetime access (billing stops, access stays) when **3 of their referrals each independently complete 6 successful $99 monthly payments** — totalling $594 paid per referral, $1,782 in referral-driven member revenue, before the referrer's lifetime kicks in. Trial months do NOT count. Refunds and chargebacks do NOT count.
4. **No alternative lifetime path.** "3 own payments → lifetime" does NOT exist. Any text saying otherwise is wrong.
5. **Cancellation:** Any time. Trial-period cancellation costs nothing. Post-trial cancellation ends billing at the close of the current period.

These are sourced from `INTEGRATION-SOURCE-OF-TRUTH.md` §9 (Decisions Log, 2026-05-02 entries). If anything in your reading conflicts with the above, the SoT wins — and report the conflict back to the manager.

---

## Step 3 — Goal of this phase

Public marketing copy and the Terms agreement must accurately describe the locked model. Currently three files lie about it. Fix all three.

---

## Step 4 — What to change (file-by-file)

### 4.1 `templates/landing.html` — FAQ rewrites

Locate the section between `<!-- 05 / FAQ -->` and `<!-- 06 / FINAL CTA -->`. Rewrite three of the six FAQ items. Leave the other three (#1 "Is this just another mastermind?", #3 "Who is this for?", #4 "Who is this NOT for?") UNCHANGED.

**FAQ #2 — "What does it cost?"**
Replace the answer with:
```
$99 / month, ongoing. Your first 30 days are free — you sign up with a card on file but no charge hits until day 31. There is no fixed end to the membership; you can cancel any time. The Society also offers Lifetime Access — but you don't buy it, you earn it. Bring three brothers into the Society. Once each one has completed six paid months ($594 each), your billing ends permanently and your seat is yours for life.
```

**FAQ #5 — "How do I get in?"**
Replace the answer with:
```
Apply through the membership page. Sign up with your card — your first 30 days are free, no charge. Stay past day 30 and your $99/month begins. We reserve the right to remove members who don't show up — but we'd much rather have you stay.
```

**FAQ #6 — "Can I cancel?"**
Replace the answer with:
```
Yes — any time. Cancelling during the 30-day trial costs you nothing; your card is never charged. After the trial converts, $99/month continues until you cancel or until you've referred three brothers who each completed six paid months — at which point your billing ends and your access becomes lifetime.
```

Match the existing HTML structure exactly (same `<div class="faq-item">` wrappers, same `<span class="faq-toggle">+</span>`, same prose voice). Keep the existing serif/mono typography — do NOT add Markdown-style emphasis or restructure the HTML.

### 4.2 `templates/pricing.html` — three fixes

**Fix A — Price typo.** Line ~57 currently reads:
```html
<span class="pricing-number">100</span>
```
Change to:
```html
<span class="pricing-number">99</span>
```

**Fix B — Add trial language.** Below the existing `<div class="pricing-tagline">Build wealth. Build character. Build together.</div>` line, insert a new element that visibly tells the user about the trial. Suggested insertion (match existing styling):
```html
<div class="pricing-trial-banner" style="margin: 0.75rem auto 0; padding: 8px 14px; background: rgba(212,175,55,0.08); border: 1px solid rgba(212,175,55,0.25); color: #D4AF37; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; letter-spacing: 2px; text-transform: uppercase; display: inline-block;">
  First 30 days free — card on file, no charge until day 31
</div>
```
Place it inside the `pricing-card-inner` div, immediately after `pricing-tagline`. Center it.

**Fix C — Add lifetime referral mechanic.** Below the existing `<p class="pricing-note">Cancel anytime. No contracts. No BS.</p>` line, ADD (do not replace) a second note describing the lifetime path:
```html
<p class="pricing-note" style="margin-top: 0.5rem;">
  Refer 3 brothers. When each completes 6 paid months, your billing stops. Lifetime access — earned, not bought.
</p>
```

Do NOT change the existing 6 feature list items, the email input, the "Have a code?" toggle, the founder code logic, or the `Join the Brotherhood` button text. Layout/CSS surgery is out of scope.

### 4.3 `templates/legal.html` — rewrite Terms §2 (Membership)

Inside the `{% if body_template == 'legal_terms' %}` branch, replace the current Section 2 block:

```html
<h2 style="color:#fff;margin-top:32px;">2. Membership</h2>
<p>Membership is $99/month for 3 months, after which lifetime access is granted at no further charge. You may cancel before the third payment to end your membership; in that case, access ends at the close of the current billing period.</p>
```

…with a new, expanded Section 2 + new Section 2A (Lifetime Access) + renumber subsequent sections accordingly. The exact replacement:

```html
<h2 style="color:#fff;margin-top:32px;">2. Membership &amp; Billing</h2>
<p>Membership is $99 USD per month, billed via Stripe to the payment method on file. Your first 30 days from signup are a free trial during which no charge is made. On day 31, your payment method is charged $99 and is then charged $99 every month thereafter until you cancel or you reach Lifetime Access (see Section 2A).</p>
<p>You may cancel at any time from your billing portal. Cancelling during the 30-day trial closes your account immediately and incurs no charge. Cancelling after the trial converts ends your access at the close of your current billing period.</p>

<h2 style="color:#fff;margin-top:32px;">2A. Lifetime Access (Referral-Earned)</h2>
<p>Sovereign Society offers Lifetime Access at no further charge to members who successfully refer at least three (3) other paying members, where each of those three referrals must independently complete six (6) consecutive months of $99 payments — a total of $594 paid by each referral, or $1,782 in total referral-driven revenue, before the referring member qualifies. Once you reach this threshold, your $99 monthly billing will be permanently terminated and your platform access becomes Lifetime, contingent on continued adherence to the Member Code of Conduct (Section 4).</p>
<p>The following do NOT count toward referral qualification: trial-period months (no payment was made); refunded payments; charged-back payments; payments made by referrals who later cancelled before reaching six successful payments. If a referral cancels before completing six payments, their progress does not transfer and is not bankable for a future re-signup.</p>
<p>There is no other path to Lifetime Access. Statements elsewhere on the website that may have suggested an alternative path are superseded by this Section.</p>
```

Then renumber all subsequent sections in the `legal_terms` branch: existing §3 (Refund Policy) becomes §3, existing §4 stays §4, etc. — actually since 2A is appended (not 3, 4, 5...), no renumber is needed. Just verify the section numbers in the legal_terms branch read 1, 2, 2A, 3, 4, 5, 6, 7, 8 in order after your edit.

Do NOT touch the `legal_privacy` branch, the `Last updated` date (a separate cleanup will refresh it), the page wrapper styling, or anything outside the `legal_terms` Section 2 area.

---

## Step 5 — What NOT to touch in this phase

- **Brand voice / hero / manifesto / pillars / tier descriptions** in `landing.html`. The non-FAQ sections of the landing are canonical.
- **`models.py` schema or properties.** The `User.has_active_subscription` bug is a separate phase (Phase 0).
- **`app.py` business logic.** Stripe wiring, GHL wiring, webhook flow — all out of scope.
- **CSS** (the gold-on-black aesthetic, the `#rain` canvas, the reveal animations, etc.).
- **Testimonials** in landing.html. Even if some are placeholders, replacing them is a marketing decision, not a copy alignment decision.
- **Stale `support@onepercentmensclub.com` email** in `legal.html` — that's tracked in §10 of the SoT and depends on the Q7 (email domain) decision which is not yet made. Leave alone.
- **The `Last updated: April 2026` date in `legal.html`.** Updating this requires a separate "diff log of legal changes" decision later. Leave alone.

---

## Step 6 — Verify before commit

Run the app locally:
```bash
python app.py
```

Open in a browser:
- `http://localhost:5000/` (landing) → scroll to FAQ → confirm #2, #5, #6 read the new copy. Confirm #1, #3, #4 unchanged.
- `http://localhost:5000/pricing` → confirm $99 (not $100), trial banner visible, lifetime referral note visible below "Cancel anytime."
- `http://localhost:5000/terms` → confirm new §2 + §2A read correctly, are properly styled, sections renumber 1, 2, 2A, 3, 4, 5, 6, 7, 8.

Search the entire repo for any remaining "$99/month for 3 months" or "$99 / month for three months" or "100" (in pricing context) strings:
```bash
grep -rn -E "(99/month for|three months|three payments|3 payments)" templates/ static/ || echo "Clean."
```

Any hits — fix them or report them.

---

## Step 7 — Commit + push

One single commit. Do not amend, do not split. Commit message verbatim:

```
phase-0a: align public copy + terms with locked business model

- landing.html: rewrite FAQ #2/#5/#6 to reflect ongoing $99/mo, 30-day
  trial, referral-only lifetime path
- pricing.html: fix $100 -> $99 typo, add trial banner, add lifetime
  referral mechanic note
- legal.html: rewrite Terms §2 (Membership & Billing) and add §2A
  (Lifetime Access) with full subscription disclosure
```

Then `git push origin main`.

---

## Step 8 — Update SoT

Open `INTEGRATION-SOURCE-OF-TRUTH.md` and:

1. In §8 Phase Status, change Phase 0A row from `⬜ pending` to `✅ done` and append `— completed 2026-MM-DD, commit <SHORT_SHA>`.
2. In §9 Decisions Log, append a new entry dated today summarizing what was changed and pasting the EXACT final FAQ #2 + Terms §2A wording committed (so future copy sessions can quote it without re-reading templates).
3. In §10 Risks, find the entry "Public copy misrepresents the offer" and STRIKE THROUGH the launch-blocker line (use Markdown `~~strikethrough~~` and append "(resolved 2026-MM-DD by phase-0a)").

Commit + push the SoT update separately:
```
sot: phase 0a complete — public copy + terms aligned
```

---

## Step 9 — Report back to the manager session

When you return to Kashi, give him a 5-bullet summary:
1. Files changed (paths + line ranges).
2. Final FAQ #2 wording (one paste, for the record).
3. Final Terms §2A wording (one paste, for the record).
4. Result of the grep for residual stale copy — clean or any hits found.
5. Any surprises (e.g., other places where the wrong model was mentioned, broken layouts spotted while testing, anything the executor noticed).

If anything in this prompt was ambiguous OR you found a conflict between this prompt and the SoT, STOP and report — do not make a judgement call on a contract-law-relevant document.
