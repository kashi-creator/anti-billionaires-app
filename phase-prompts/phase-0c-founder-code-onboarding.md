# Phase 0C — Wire the Founder-Code Onboarding Path

> Paste this entire prompt into a fresh Claude Code session opened in `~/anti-billionaires-app`. **One narrow goal:** make the existing `/pricing` founder-code UI actually create accounts on the server side. No other changes.
>
> Surfaced 2026-05-02 by manager session. The audit didn't catch it: `templates/pricing.html` has a working JS path that validates a code, but no server endpoint creates an account from a valid code. Founder-coded users currently get stuck — the "✓ Code applied — free access" button still calls the broken `/create-checkout-session` path.

---

## Step 0 — Pull before reading

```bash
git fetch origin && git status
```

If `main` is behind origin: `git reset --hard origin/main` (after confirming no uncommitted local work).

---

## Step 1 — Read first (mandatory)

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — full file. Pay attention to §1 (live URL is `https://anti-billionaires-app-production.up.railway.app`), §6 (GHL tag taxonomy is mid-migration; for THIS phase use the current legacy tags `["Lifetime", "ABMC"]` to match the rest of the codebase — Phase 1 will normalize all of them at once), §7 (customer journey), §13.2 (Stripe state — confirms the signup→pricing→stripe flow is currently the canonical path).
2. `app.py:760-802` — current `/signup` route, what it does today.
3. `app.py:1228-1234` — current `/validate-code` route.
4. `app.py:1237-1271` — current `/create-checkout-session` route (the one the founder-code button is currently misrouted to).
5. `app.py:1593-1620` (approximately) — `admin_grant_lifetime` route. **This is the operational pattern you mirror** — same field flips, same email send, same GHL push.
6. `templates/pricing.html` lines 100-219 — the current pricing UI, especially the JS handlers at `apply-code-btn` (line 140) and `checkout-btn` (line 170).
7. `email_send.py` — confirm `send_lifetime_unlocked` exists and what it expects.

---

## Step 2 — The decisions this phase encodes (manager has locked these)

### 2.1 Founder code semantics

A valid founder code grants the entered email a **fully-active lifetime account**, no payment, no trial. Specifically:
- `User.lifetime_access = True`
- `User.subscription_status = "active"`
- `User.lifetime_qualified_at = datetime.utcnow()`
- `User.email_verified = True` (skip the verification email; comps shouldn't be friction-tested)
- `User.is_admin = False` (admin status is granted manually via `/admin` panel after creation — keeps the code itself from being an admin escalation vector if leaked)

### 2.2 Code source

Reuse the existing env-var pattern at `app.py:1231`:
```python
founder_codes = os.environ.get("FOUNDER_CODES", os.environ.get("FOUNDER_CODE", "ABMC2026")).split(",")
```
Already supports comma-separated multiple codes. **Do NOT change this — extract it into a small helper that both `/validate-code` and the new `/signup-with-code` use, so the source of truth stays single.**

Helper:
```python
def _valid_founder_codes() -> list[str]:
    raw = os.environ.get("FOUNDER_CODES") or os.environ.get("FOUNDER_CODE") or "ABMC2026"
    return [c.strip() for c in raw.split(",") if c.strip()]

def _is_founder_code(code: str) -> bool:
    return code.strip() in _valid_founder_codes()
```
Refactor `/validate-code` to use the helper. Keep the helper in `app.py` near the existing route — don't lift to a new file (lifting cross-cutting helpers is Phase 1's job, not 0C's).

### 2.3 Welcome email

Send `send_lifetime_unlocked(user)` immediately on account creation. Reasoning: founder-coded users ARE lifetime accounts; the existing email template fits their semantic state and avoids creating yet another email template just for this path.

If `RESEND_API_KEY` is unset (current production state — Tier 1 setup hasn't happened yet), the `_send_now` fallback in `email_send.py` already prints to stdout and doesn't crash. Don't special-case anything here — let the existing graceful degradation handle it.

### 2.4 GHL push on creation

Call `ghl_upsert_contact(email, name, tags=["Lifetime", "ABMC"])`. Yes, `["ABMC"]` is legacy and Phase 1 will normalize this to the canonical stage tag `lifetime-qualified` — but consistency with the rest of the current codebase matters more than getting a head start on the rename, because Phase 1's backfill script sweeps everything at once. **DO NOT introduce the new canonical taxonomy here — that's a Phase 1 decision and crossing the boundary creates a half-migrated state.**

### 2.5 What does NOT happen in this phase

- Do NOT change `models.py`. The four boolean/timestamp fields all already exist.
- Do NOT touch `/signup` — that route stays as-is for the future paid-trial flow (Stripe will use it in the post-checkout success handler).
- Do NOT modify the GHL tag taxonomy, the GHL client location, or any Stripe wiring.
- Do NOT add admin-elevation logic to the founder code. Admin = manual flip in `/admin` panel.
- Do NOT add CAPTCHA, rate-limit, or anti-abuse gating beyond what `flask-limiter` already does on `/signup`. (Founder codes ARE the abuse gate — invalidates if the code itself stays private.)
- Do NOT remove the existing `/create-checkout-session` Stripe placeholder check — Stripe wiring is happening in parallel and will exit that branch the moment `STRIPE_SECRET_KEY` is set in Railway env. Both paths must coexist.

---

## Step 3 — Implementation

### 3.1 `/signup-with-code` POST endpoint in `app.py`

Goes near the existing `/signup` route (right after it is fine). Pattern:

```python
@app.route("/signup-with-code", methods=["POST"])
@limiter.limit("5 per minute")  # match /signup's anti-abuse posture
@require_csrf
def signup_with_code():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    code = (data.get("code") or "").strip()

    if not name or not email or not password or not code:
        return jsonify({"error": "All fields are required."}), 400
    if len(password) < 10:
        return jsonify({"error": "Password must be at least 10 characters."}), 400
    if not _is_founder_code(code):
        return jsonify({"error": "Invalid founder code."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists. Please log in."}), 400

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(
        name=name,
        email=email,
        password_hash=hashed,
        points=0,
        streak_days=1,
        last_login_date=date.today(),
        subscription_status="active",
        lifetime_access=True,
        lifetime_qualified_at=datetime.utcnow(),
        email_verified=True,
    )
    user.ensure_referral_code()
    db.session.add(user)
    db.session.commit()

    # GHL push — legacy taxonomy; Phase 1 normalizes
    ghl_upsert_contact(email, name, tags=["Lifetime", "ABMC"])

    # Welcome email — graceful degrade if Resend unset
    try:
        send_lifetime_unlocked(user)
    except Exception as e:
        app.logger.warning("send_lifetime_unlocked failed (non-fatal): %s", e)

    # Auto-login + redirect
    login_user(user, remember=True)
    return jsonify({"redirect": url_for("phase3.welcome")})
```

The redirect target `phase3.welcome` is the existing onboarding checklist route (`/welcome`). Confirm it exists by grep before pasting; if the blueprint name differs, adjust.

### 3.2 Update `templates/pricing.html` JS to use the new endpoint

Two changes in the existing `<script>` block:

**Change 1** — when code is valid, capture the validated code in a variable AND prompt the user to enter name+password. Currently the validate path just changes the button text. We need a small inline form or a redirect into `/signup-with-code`.

The cleanest UX without rebuilding the page: when code applies, swap the email field into a small 3-field mini-form (name, email, password — email is reused if already entered) styled to match the existing inputs. Submit hits `/signup-with-code`.

Pattern (apply inside the existing `apply-code-btn` click handler, after the current `if (data.valid)` block):

```javascript
if (data.valid) {
    // Existing UI changes (button → "Code applied", color, etc.) stay.

    // Replace the email-only field with a mini founder signup form
    const emailField = document.getElementById('pricing-email');
    const parent = emailField.parentElement;
    parent.innerHTML = `
        <input type="text" id="founder-name" placeholder="Your name" required style="...">
        <input type="email" id="founder-email" placeholder="Email" value="${emailField.value}" required style="...">
        <input type="password" id="founder-password" placeholder="Password (10+ chars)" minlength="10" required style="...">
    `;
    // Re-bind the main CTA to the founder submit handler
    document.getElementById('checkout-btn').dataset.founder = 'true';
}
```

(Style strings should match the existing `padding:10px 14px;border:1px solid #333;border-radius:8px;background:#1a1a1a;color:#fff;font-size:0.9rem;` from line 108. Inline-styled to avoid touching `style.css` in this phase.)

**Change 2** — branch the main CTA click handler on `dataset.founder === 'true'`:

```javascript
document.getElementById('checkout-btn').addEventListener('click', async function() {
    if (this.dataset.founder === 'true') {
        // Founder code path
        const name = document.getElementById('founder-name').value.trim();
        const email = document.getElementById('founder-email').value.trim();
        const password = document.getElementById('founder-password').value;
        const code = document.getElementById('coupon-code').value.trim();
        if (!name || !email || !password || !code) {
            alert('Fill in name, email, and password.');
            return;
        }
        const r = await fetch('/signup-with-code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name=csrf-token]')?.content || '',
            },
            body: JSON.stringify({ name, email, password, code }),
        });
        const result = await r.json();
        if (result.redirect) {
            window.location.href = result.redirect;
        } else {
            alert(result.error || 'Something went wrong.');
        }
        return;
    }

    // Existing Stripe path — UNCHANGED below this line.
    const email = document.getElementById('pricing-email').value.trim();
    if (!email) { /* ... existing logic ... */ }
    /* ... rest of existing handler ... */
});
```

Critical: do not delete or restructure the existing Stripe path. Just prepend the founder branch.

### 3.3 CSRF meta tag

The fetch above expects a CSRF token meta tag in the page. Confirm `templates/base.html` has `<meta name="csrf-token" content="{{ csrf_token() }}">` in `<head>`. If it doesn't, add it. (`csrf_token` is already a context processor per `app.py:111`, so `{{ csrf_token() }}` resolves.)

If `pricing.html` does NOT extend `base.html`, add the meta directly into `pricing.html`'s `<head>` block instead.

### 3.4 Smoke tests (local)

1. `python app.py` — server starts, no import errors.
2. With `FOUNDER_CODE=TESTABMC2026 python app.py` — set a known code locally.
3. Navigate to `http://localhost:5050/pricing` (or whatever PORT). Click "Have a code?". Enter `TESTABMC2026`. Confirm:
   - Code accepts (button changes color/text)
   - Form swaps to 3 fields (name, email, password)
   - Submitting valid name/email/password → redirects to `/welcome`
   - Account is created with `lifetime_access=True` (verify in `flask shell`: `User.query.filter_by(email=...).first().lifetime_access`)
   - `subscription_status == "active"`
   - `email_verified == True`
   - `lifetime_qualified_at` is set
4. Try wrong code → "Invalid founder code." returned.
5. Try empty fields → "All fields are required." returned.
6. Try short password → "Password must be at least 10 characters."
7. Try existing email → "An account with this email already exists."
8. After successful signup, hit `/feed` — no paywall (lifetime access bypasses).
9. Hit `/billing-portal` — should redirect or 404 gracefully (Stripe portal won't open for a lifetime account; just confirm it doesn't crash).
10. Confirm GHL push attempted (in dev with no env, you'll see the threading.Thread fire and silently no-op — acceptable). Lifetime email send: in dev with no `RESEND_API_KEY`, you'll see the stdout fallback print.

### 3.5 What to leave alone

- `/signup` (paid path)
- `/create-checkout-session` (Stripe path — keep its placeholder branch intact for the moment Stripe is wired)
- `/validate-code` (after refactor to use helper, keep the public endpoint — pricing.html still calls it for the front-end-only "is this code valid" check)
- All admin routes (`/admin/*`)
- Any other template, route, or model

---

## Step 4 — Update SoT

In `INTEGRATION-SOURCE-OF-TRUTH.md`:

- **§8 Phase Status** — add a row for **0C** between 0B and 1, mark ✅ done with commit SHA.
- **§9 Decisions Log** — append: founder-code semantics locked (lifetime + active + email_verified), code source single helper, mini-form UX, GHL legacy tags retained for Phase 1 sweep.
- **§10 Risks** — strike-through the implicit gap (which is not currently logged because the audit missed it). Add a new entry above the strike-through that says: "**[2026-05-02 audit gap]** The Phase 0 audit missed that `/pricing` founder-code UI had no server-side handler. Resolved by Phase 0C in same-day commit." This serves as a prompt for future audits to test full UI flows, not just route grep.
- **§13** is the audit appendix from Phase 0 — leave it; Phase 0C is independent of the audit's findings.

---

## Step 5 — Commit + push

Two commits, atomic:

**Commit 1 — code path:**
```
phase-0c: wire founder-code onboarding (server side + pricing.html)

- new /signup-with-code POST route — creates lifetime account from valid code
- pricing.html: founder-code path swaps email field for 3-field mini-form
- founder code source extracted to _is_founder_code() helper
- /validate-code refactored onto the helper for single source of truth
```
Stage exactly: `app.py`, `templates/pricing.html`, `templates/base.html` (only if you added the CSRF meta tag).

**Commit 2 — SoT:**
```
phase-0c: sot — founder-code onboarding shipped, audit-gap logged
```
Stage exactly: `INTEGRATION-SOURCE-OF-TRUTH.md`.

Push after each, or batch.

---

## Step 6 — Report back to manager

5-bullet summary:

1. **Endpoint** — `/signup-with-code` shipped (commit SHA), all 10 smoke tests pass.
2. **UX** — pricing.html branches correctly: code-applied path swaps to mini-form, Stripe path unchanged.
3. **Helper** — `_is_founder_code()` is single source of truth; `/validate-code` refactored.
4. **GHL + email** — legacy `["Lifetime", "ABMC"]` tags applied (Phase 1 sweeps); `send_lifetime_unlocked` called with graceful degrade.
5. **Surprises / new launch blockers** — anything that demands a manager decision.

If anything in this prompt is ambiguous or the work surfaces an architectural question (e.g., the `/welcome` blueprint route doesn't exist, the CSRF meta tag is in a different spot, or the `email_verified` field has a downstream side effect I haven't anticipated), STOP and report — do not decide.
