# Phase 10 — Form-submit UX fixes (post composer + profile photo)

> Paste into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Two narrow UX fixes.** Both are template/JS-only — no models, no migrations, no env changes. ~20 min total.
>
> Surfaced 2026-05-09 by Kashi: posted the same content 3× because the post button doesn't disable on click, and noticed the profile-photo file input has no preview.

---

## Step 0 — Pull

```bash
git fetch origin && git status
```
Reset hard if behind.

---

## Step 1 — Read first

1. `templates/feed.html` lines 54–96 (the post composer form). The form is a vanilla HTML POST with `enctype="multipart/form-data"`. Server returns a 302 redirect after `flash("Post published.", "success")`.
2. `templates/feed.html` JS section — find `previewPostImage()` and `clearPreview()`. The post composer already has an in-JS image preview helper. Profile edit needs the same pattern.
3. `templates/edit_profile.html` lines 1–35 (full file is short). Note the `<input type="file" id="profile_photo">` has no `onchange` handler and no preview wiring.
4. `templates/base.html` lines 339–349 — flash rendering. Auto-dismiss timing is in the inline JS around line 394.
5. `app.py:1171-1208` — `create_post` handler. Don't change. Just confirming it does redirect + flash.
6. `app.py:edit_profile` (grep for it) — same. Server side is fine.

---

## Step 2 — Decisions locked

### 2.1 Issue 1: Post composer button + reset

The fix has two parts, both client-side:

**(a) Disable submit button on click + show "Posting..." state.** Prevents the double/triple-click → duplicate-post bug.

**(b) Visually clear the composer (textarea + photo preview) AT SUBMIT TIME.** Even though the redirect would do this anyway via fresh page load, immediate clear gives the user instant "yes, it went through" feedback while the server processes (~500ms typical roundtrip).

Implementation: a single `submit` event listener on `#postForm`. Disable button, set text to "Posting...", clear textarea, clear preview. Don't `preventDefault()` — the form still submits natively.

```javascript
document.getElementById('postForm')?.addEventListener('submit', function(e) {
    const btn = this.querySelector('button[type="submit"]');
    if (!btn || btn.disabled) {
        // Already submitting — block double-fire
        e.preventDefault();
        return;
    }
    btn.disabled = true;
    btn.textContent = 'Posting...';
    // Visual reset (form still submits natively before the page redirects)
    setTimeout(() => {
        document.getElementById('postContent').value = '';
        clearPreview();
        const pollCreator = document.getElementById('pollCreator');
        if (pollCreator) pollCreator.style.display = 'none';
    }, 50);
});
```

The 50ms `setTimeout` lets the form's serialization complete before we wipe the textarea. Without it, the textarea would clear before the form data is captured.

### 2.2 Issue 2: Profile photo preview

When the user picks a file in `/profile/edit`, swap the avatar `<img>` src to a local `URL.createObjectURL(file)` blob URL. Visual feedback before save.

Add to `edit_profile.html` in a `{% block scripts %}` block at the bottom (or inline `<script>` if the template doesn't currently use `{% block scripts %}`):

```javascript
document.getElementById('profile_photo')?.addEventListener('change', function(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const avatar = document.querySelector('.avatar.avatar-xl');
    if (!avatar) return;
    // Replace the avatar's contents with a fresh <img>
    const url = URL.createObjectURL(file);
    avatar.innerHTML = `<img src="${url}" alt="">`;
});
```

Note: the existing avatar div at line 12 contains either an `<img>` (if photo set) or a `<span>` (initial letter). We replace its inner HTML uniformly to handle both cases.

### 2.3 What does NOT happen here

- Do NOT switch the post form to AJAX/fetch. Vanilla form POST is fine; the only client-side issue is button state + visual reset.
- Do NOT change flash auto-dismiss timing or move the flash container. That's a separate UX concern.
- Do NOT add the same preview pattern to other photo upload sites (event create, win create, deal create, etc.). Out of scope. Only post composer (already has preview) and profile edit (this phase).
- Do NOT touch any server route, model, migration, or env var.
- Do NOT modify `static/js/app.js`. Both JS additions are inline in their respective templates (close to the form they affect, easier to maintain).
- Do NOT touch onboarding step 1 photo upload. Onboarding has its own photo-preview JS (around `templates/onboarding.html` line 152-162); it already works.

---

## Step 3 — Implementation

### 3.1 `templates/feed.html` — add post-form submit handler

Find the existing `<script>` block where `previewPostImage`, `clearPreview`, `togglePollCreator`, `addPollOption` etc. are defined. Add the submit handler from §2.1 in the same block.

If feed.html uses `{% block scripts %}` (check the bottom), put the new code in that block. Otherwise add inline.

### 3.2 `templates/edit_profile.html` — add file-change handler

Add the JS from §2.2 at the bottom of the template inside `{% block scripts %}` (if used) or inline `<script>` at the end of the form.

Confirm the parent `base.html` has a `{% block scripts %}` placeholder near the closing `</body>`. If it doesn't, just inline `<script>` after the closing `</form>` tag.

---

## Step 4 — What NOT to break

- The post form must still submit natively (no `preventDefault`). The redirect is what shows the new post in the feed.
- `previewPostImage()` and `clearPreview()` must still work after these changes — they're called on the photo input change AND from the new submit handler.
- Profile edit page must still function for the no-photo-uploaded case — submit succeeds, photo stays as-is.
- Polls, comments, and all other feed interactions stay untouched.
- No console errors on either page after the changes (run with browser devtools open during smoke test).

---

## Step 5 — Smoke tests

Local Flask:

1. **Post double-click test:** type "test post 1" in composer. Click Post button. Immediately try to click again — button is disabled, says "Posting...". After redirect, only ONE post appears in the feed. ✓
2. **Post with photo test:** type "test post 2", attach a photo, click Post. Photo preview clears, textarea clears, button disables, redirect happens, new post with photo appears in feed. ✓
3. **Post without photo test:** type "test post 3", click Post. Same flow, no photo. ✓
4. **Poll-creator-open test:** open poll creator, fill in question + options, click Post. Poll creator div hides at submit time. After redirect, post + poll appear correctly. ✓
5. **Profile photo preview test:** go to `/profile/edit`. Note current avatar (initial or existing photo). Click "Change Photo", pick a different image. Avatar IMMEDIATELY updates to show the new image (preview blob URL). Click Save Changes. After redirect, the new image is the actual saved profile photo. ✓
6. **Profile photo cancel test:** go to `/profile/edit`, pick a photo (preview shows). Click Cancel link instead of Save. Lands on `/profile/<id>` with the OLD photo still — no upload happened. ✓
7. **Browser devtools console:** zero errors on /feed and /profile/edit during the above flows.

Production verification (after deploy):

8. Same flows on `https://anti-billionaires-app-production.up.railway.app/feed` and `/profile/edit`. The R2 upload pipeline (Phase 9) is unaffected — file lands in R2 just like before; the only change is the client-side preview.

---

## Step 6 — Update SoT

- §3 App Scope: no change.
- §8 Phase Status: add Phase 10 ✅ done with commit SHA.
- §9 Decisions Log: append entry — locked client-side UX patterns: (1) disable-on-submit + visual reset for any feed/social form-POST, (2) `URL.createObjectURL` preview for any user-facing file input that doesn't already have one. Future audit point: walk every `<input type="file">` in templates and check whether it has a preview. Items without one are UX debt.
- §10 Risks: no new risks.

---

## Step 7 — Commit + push

Single commit (small enough, all template-only):

```
phase-10: form-submit ux — post button disables; profile photo previews

- feed.html: postForm submit handler disables button, clears textarea +
  preview + poll-creator at submit time. Prevents double-click duplicate
  posts (kashi posted same content 3x on 2026-05-09 because of this).
- edit_profile.html: profile_photo onchange swaps avatar to blob URL
  preview immediately. User sees new photo before clicking Save.
- No server changes. R2 upload pipeline (phase 9) unaffected.
```

Stage exactly: `templates/feed.html`, `templates/edit_profile.html`, `INTEGRATION-SOURCE-OF-TRUTH.md`.

Push.

---

## Step 8 — Report back

5 bullets:

1. **feed.html** — submit handler added at line N in script block. Verified smoke 1-4 pass.
2. **edit_profile.html** — file-change handler added at line N. Verified smoke 5-6 pass.
3. **Console errors** — zero on both pages.
4. **Live verification** — prod smoke test result (after Railway redeploy completes).
5. **Surprises / blockers** — anything (e.g. the existing post composer already had a half-implemented submit handler; the avatar element selector misses on a variant; an inline form on a different page also needs the fix and you stopped to flag).

If anything is genuinely unclear, STOP and report — don't extend scope.
