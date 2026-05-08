# Phase 9 — Migrate file uploads from Railway disk to Cloudflare R2

> Paste into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Goal:** profile photos and post images survive Railway redeploys. Currently every deploy wipes `/app/static/uploads/` so user-uploaded photos go 404 within hours of upload.
>
> R2 bucket already created (`mensgroupapp`), credentials already in Railway env (manager session 2026-05-08). Live R2 access verified via boto3 round-trip test.

---

## Step 0 — Pull

```bash
git fetch origin && git status
```
Reset hard if behind: `git reset --hard origin/main`.

---

## Step 1 — Read first

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — full file. The "Railway wipes /app/static/uploads" gotcha in §10 is the root cause being addressed here.
2. `app.py` — the `save_upload()` helper (around line 175-185) is the entry point you'll refactor. Also the `UPLOAD_FOLDER` config + `ALLOWED_EXTENSIONS`.
3. `app.py` `create_post`, `create_event`, `signup`, `edit_profile`, onboarding step 1 — every place that calls `save_upload()` and stores the returned path.
4. Any template that renders user-uploaded media via `url_for('static', filename=user.profile_photo)` — these need to switch to a helper that routes `uploads/...` to R2.
5. `requirements.txt` — you'll add `boto3`.

---

## Step 2 — Decisions locked

### 2.1 Storage path conventions

- All user-uploaded files live in R2 bucket `mensgroupapp` under key prefix `uploads/`.
- DB column values stay the same: `User.profile_photo`, `Post.image_path`, etc. continue to store strings like `uploads/<uuid>.<ext>`. **No schema change.** Just the meaning shifts: previously the prefix was relative to the local `static/` dir; now it's the R2 object key.
- Files committed to the repo (e.g. `static/img/seed/space-*.png`, CSS, JS) stay served from Railway via `url_for('static', ...)`. Only the `uploads/...` paths route to R2.

### 2.2 URL generation strategy: pre-signed URLs

- R2 buckets without a custom domain don't allow public access (Cloudflare deprecated `r2.dev` public for new accounts unless you bring a Cloudflare-DNS-managed domain — which Sovereign Society doesn't yet have because Bryce hasn't switched nameservers at GoDaddy).
- Solution: server generates short-lived **pre-signed URLs** for each photo render. URL expires in 1 hour. Browser caches it for the page session. Re-renders generate fresh URLs.
- Trade-off: one boto3 `generate_presigned_url` call per photo per page render. Cheap (~1ms, no network). Acceptable for current scale.
- Alternative considered + rejected: Flask-side proxy (route `/u/<filename>` that fetches from R2 and streams to client). Adds Railway egress cost + latency. Skip.
- Future enhancement: when Bryce switches nameservers and `media.sovereignsociety.rich` becomes a Cloudflare-DNS domain, attach it as a custom domain on the R2 bucket → swap pre-signed URLs for permanent public URLs. Out of scope for this phase.

### 2.3 Local-dev fallback

If `R2_ACCESS_KEY_ID` is unset in env (i.e., running locally without R2 creds), `save_upload()` falls back to disk write at `static/uploads/<uuid>.<ext>` and the URL helper falls back to `url_for('static', filename=path)`. This keeps dev workflow simple — devs don't need R2 creds locally, can use the existing local-disk pattern.

### 2.4 Migration of existing broken paths

Production DB has 5 User rows with `profile_photo='uploads/<hash>.<ext>'` where the file is gone (Railway wiped). Migrate-script: for each User row with a non-NULL `profile_photo` whose key doesn't exist in R2, NULL the column. Affected users will see avatar placeholders + can re-upload via `/profile/edit` after this phase ships.

Run as one-shot Python script invoked from `railway run` (manager session does this after the code lands).

### 2.5 R2 env vars (already set on Railway by manager)

| Var | Value |
|---|---|
| `R2_ACCESS_KEY_ID` | (32 hex chars, set) |
| `R2_SECRET_ACCESS_KEY` | (64 hex chars, set) |
| `R2_ENDPOINT` | `https://442b4faf52096e6b6cd181b3f0c5b887.r2.cloudflarestorage.com` |
| `R2_BUCKET` | `mensgroupapp` |

For local testing, you can pull these via `railway variables --service anti-billionaires-app --json` or run Python through `railway run` (which injects the env).

### 2.6 What does NOT happen here

- Do NOT add a custom domain (`media.sovereignsociety.rich` etc.) — gated on Bryce's DNS switch.
- Do NOT migrate seed images (`static/img/seed/space-*.png`) — they stay in the repo, served from Railway. Only user-uploaded paths route to R2.
- Do NOT add image-processing (resize, thumbnails, etc.). Out of scope. Files go to R2 as-is.
- Do NOT delete `static/uploads/` directory from disk — keep it as the dev-mode fallback target.
- Do NOT change `ALLOWED_EXTENSIONS` or `MAX_CONTENT_LENGTH`. Same upload validation rules.
- Do NOT touch the seed_placeholders.py or _seed_content() — those generate paths into `img/seed/`, not `uploads/`.

---

## Step 3 — Implementation

### 3.1 `requirements.txt`

Add `boto3` (let pip pick a recent version, e.g. `>=1.34`).

### 3.2 `lib/r2.py` (new file)

```python
"""Cloudflare R2 client wrapper. R2 is S3-compatible — uses boto3.

Env vars consumed:
    R2_ACCESS_KEY_ID
    R2_SECRET_ACCESS_KEY
    R2_ENDPOINT       — full URL, no trailing slash
    R2_BUCKET         — bucket name

If any of those is unset, `enabled()` returns False and callers fall back
to local-disk storage for dev workflow.
"""
import os
import logging
from typing import Optional, IO

log = logging.getLogger(__name__)

# Cache the boto3 client across calls — instantiation is non-trivial.
_client_cache = None


def enabled() -> bool:
    return all(os.environ.get(k) for k in (
        "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET"
    ))


def _client():
    global _client_cache
    if _client_cache is None:
        import boto3
        from botocore.client import Config
        _client_cache = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
    return _client_cache


def upload_fileobj(fileobj: IO[bytes], key: str, content_type: Optional[str] = None) -> bool:
    """Upload to R2 under the given key. Returns True on success, False on error."""
    if not enabled():
        return False
    extra = {"ContentType": content_type} if content_type else {}
    try:
        _client().upload_fileobj(fileobj, os.environ["R2_BUCKET"], key, ExtraArgs=extra)
        return True
    except Exception as e:
        log.warning("r2.upload_fileobj failed for %s: %s", key, e)
        return False


def presigned_url(key: str, expires: int = 3600) -> Optional[str]:
    """Return a time-limited download URL for a key, or None if R2 unavailable."""
    if not enabled() or not key:
        return None
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": os.environ["R2_BUCKET"], "Key": key},
            ExpiresIn=expires,
        )
    except Exception as e:
        log.warning("r2.presigned_url failed for %s: %s", key, e)
        return None


def head_object(key: str) -> bool:
    """True if the key exists in R2."""
    if not enabled():
        return False
    try:
        _client().head_object(Bucket=os.environ["R2_BUCKET"], Key=key)
        return True
    except Exception:
        return False


def delete_object(key: str) -> bool:
    if not enabled() or not key:
        return False
    try:
        _client().delete_object(Bucket=os.environ["R2_BUCKET"], Key=key)
        return True
    except Exception as e:
        log.warning("r2.delete_object failed for %s: %s", key, e)
        return False
```

### 3.3 Refactor `save_upload()` in `app.py`

Existing function (around line 175):

```python
def save_upload(file):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        return f"uploads/{filename}"
    return None
```

Replace with:

```python
def save_upload(file):
    if not (file and allowed_file(file.filename)):
        return None
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    key = f"uploads/{filename}"
    from lib import r2
    if r2.enabled():
        # Stream straight to R2; rewind the FileStorage cursor first.
        file.stream.seek(0)
        content_type = file.mimetype or "application/octet-stream"
        if r2.upload_fileobj(file.stream, key, content_type=content_type):
            return key
        # If R2 push fails, fall through to local-disk write so the user
        # still gets their file saved (degraded but not dropped).
        log.warning("R2 upload failed for %s; falling back to local disk.", key)
        file.stream.seek(0)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    return key
```

### 3.4 Template helper `asset_url()`

Add this Jinja-callable in `app.py` near the existing context processors (around line 110):

```python
@app.context_processor
def _inject_asset_url():
    from lib import r2

    def asset_url(path):
        """Resolve a file path to a renderable URL.

        - None / empty → empty string (caller renders placeholder)
        - 'img/seed/...' or any non-uploads/ path → static URL (committed asset)
        - 'uploads/...' AND R2 enabled → pre-signed R2 URL (1-hour expiry)
        - 'uploads/...' AND R2 disabled → static URL (local-dev fallback)
        """
        if not path:
            return ""
        if path.startswith("uploads/") and r2.enabled():
            url = r2.presigned_url(path, expires=3600)
            if url:
                return url
        return url_for("static", filename=path)

    return {"asset_url": asset_url}
```

### 3.5 Update templates that render user-uploaded media

Find every `url_for('static', filename=<user-upload-field>)` and replace with `asset_url(<user-upload-field>)`. Affected fields:
- `User.profile_photo`
- `Post.image_path`
- `Story.image_path`
- `Win.image_path`
- `Deal.image_path`
- `Reel.thumbnail_path`
- `ChallengeSubmission.image_path`
- `Event.cover_image` — **conditional**: if path starts with `uploads/` use `asset_url`, if `img/seed/` keep static. The new helper handles both cases automatically — just swap call sites.
- `Space.cover_image` — same conditional handling.
- `Course.cover_image` — same.

Easier rule: at every `url_for('static', filename=X)` site where `X` could come from a model field that gets populated by `save_upload()`, swap to `asset_url(X)`. The helper internally decides static-vs-R2.

Grep to find all call sites:
```bash
grep -rn "url_for('static', filename=" templates/ app.py phase3_routes.py features_routes.py
```

Audit each: if the filename is a fixed asset (CSS, JS, hardcoded image like `img/sovereign-logo.png`), keep `url_for('static', ...)`. If it's a model field that could have been uploaded, swap to `asset_url(field)`.

### 3.6 Migration script for broken paths

Create `scripts/null_broken_uploads.py`:

```python
"""Null out User.profile_photo paths whose R2 key (or local file) doesn't exist.

Run after Phase 9 ships so the 5 users with broken paths from Railway's
ephemeral-disk era get clean placeholders + can re-upload.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app
from models import db, User
from lib import r2

with app.app_context():
    users = User.query.filter(User.profile_photo.isnot(None)).all()
    nulled = 0
    for u in users:
        path = u.profile_photo
        # Check both R2 and local disk
        if path.startswith("uploads/") and r2.enabled() and r2.head_object(path):
            continue
        local_path = os.path.join(app.config["UPLOAD_FOLDER"], path.removeprefix("uploads/"))
        if os.path.exists(local_path):
            continue
        print(f"NULL: user {u.id} ({u.email}) had {path}")
        u.profile_photo = None
        nulled += 1
    db.session.commit()
    print(f"Nulled {nulled} of {len(users)} profile_photo paths.")
```

DO NOT RUN THIS DURING THE PHASE. Manager session runs it post-deploy via `railway run` against prod DB.

Also update `scripts/README.md` with a stanza for this script.

### 3.7 Smoke tests (local Flask)

Run these BEFORE committing.

```bash
# 1. boto3 installed, lib imports cleanly
.venv/bin/python -c "from lib import r2; print('enabled (no env):', r2.enabled())"
# Expected: 'enabled (no env): False'

# 2. With R2 env present, enabled() returns True
PUBLIC_DB=$(railway variables --service Postgres --json | python3 -c "import json,sys; print(json.load(sys.stdin)['DATABASE_PUBLIC_URL'])")
railway run sh -c "DATABASE_URL='$PUBLIC_DB' .venv/bin/python -c 'from lib import r2; print(\"enabled:\", r2.enabled())'"
# Expected: 'enabled: True'

# 3. End-to-end roundtrip
railway run sh -c "DATABASE_URL='$PUBLIC_DB' .venv/bin/python -c '
from lib import r2
from io import BytesIO
ok = r2.upload_fileobj(BytesIO(b\"test\"), \"uploads/_phase9_smoke.txt\", content_type=\"text/plain\")
print(\"upload:\", ok)
print(\"presigned:\", bool(r2.presigned_url(\"uploads/_phase9_smoke.txt\")))
print(\"head:\", r2.head_object(\"uploads/_phase9_smoke.txt\"))
print(\"delete:\", r2.delete_object(\"uploads/_phase9_smoke.txt\"))
'"
# Expected: all True

# 4. Local dev: python app.py (no R2 env) → upload still works to disk
unset R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_ENDPOINT R2_BUCKET
python app.py &
sleep 3
# Visit /profile/edit, upload a photo, verify it lands in static/uploads/ on disk and the field stores 'uploads/<hash>.<ext>'
kill %1
```

### 3.8 What NOT to break

- Existing `/static/img/seed/...` URLs must still work (they're not uploads, served from disk).
- CSS/JS via `url_for('static', filename='css/style.css')` etc. must still work.
- Local `python app.py` development must still work without R2 env (degraded to disk write).
- Photo uploads from before this phase still in DB but file gone in R2 → render path returns the broken URL; member sees broken image. Manager will null these post-deploy via the migration script.

---

## Step 4 — Update SoT

- §3 App Scope: add note "User uploads → Cloudflare R2 bucket `mensgroupapp` (Phase 9)."
- §5 Env Vars: add R2_* entries to "Currently expected" table.
- §8 Phase Status: Phase 9 ✅ done with commit SHA.
- §9 Decisions Log: append entry — pre-signed URL strategy, 1-hour expiry, local-disk fallback for dev, future custom-domain enhancement gated on Bryce DNS switch.
- §10 Risks:
  - Strikethrough the "Railway wipes /app/static/uploads" gotcha — resolved.
  - Add: "Pre-signed URL renders cost ~1ms boto3 call per photo per page render. Cheap at current scale; if /feed grows to 100+ photos per render, consider caching pre-signed URLs in `g` per-request."
  - Add: "R2 bucket `mensgroupapp` is on Bryce's Cloudflare account — same ownership pattern as Stripe and GHL. Document in BRYCE-HANDOFF.md."

---

## Step 5 — Commit + push

Three commits:

**Commit 1 — boto3 + lib:**
```
phase-9: add boto3 + lib/r2.py for cloudflare r2 storage

R2 client wrapper with upload_fileobj, presigned_url, head_object, delete.
Cached client. enabled() returns False if any of 4 env vars unset, so
local dev (no R2 creds) gracefully falls back to disk.
```
Stage exactly: `requirements.txt`, `lib/r2.py`.

**Commit 2 — save_upload + asset_url + templates:**
```
phase-9: save_upload pushes to r2; asset_url helper routes uploads/ → r2

- save_upload: streams to r2 if enabled, falls back to disk on failure or
  when r2 unavailable (local dev).
- new asset_url() context processor — routes 'uploads/...' paths through
  presigned_url, leaves static asset paths (img/seed/, css/, js/) on the
  url_for('static', ...) flow.
- templates audited and updated at every site rendering a user-uploaded
  field. Static asset references unchanged.
```
Stage exactly: `app.py`, every modified template.

**Commit 3 — migration script + sot:**
```
phase-9: scripts/null_broken_uploads.py + sot — r2 uploads live
```
Stage exactly: `scripts/null_broken_uploads.py`, `scripts/README.md`, `INTEGRATION-SOURCE-OF-TRUTH.md`.

Push.

---

## Step 6 — Report back to manager

7 bullets:

1. **boto3 + lib/r2.py shipped** — commit SHA, all 4 helper functions covered.
2. **save_upload refactored** — flow described, fallback verified.
3. **asset_url helper** — in context processor, exposed to all templates.
4. **Templates updated** — list of files touched + count of `url_for('static', ...)` → `asset_url(...)` swaps.
5. **Smoke tests** — 4 results from Step 3.7.
6. **Live verification (after deploy):** load `/profile/edit` for the admin account, upload a photo, refresh `/feed`, confirm the new photo renders. Then check R2 bucket contents (manager will help via boto3 from manager session) — should see the new `uploads/<hash>.<ext>` key.
7. **Surprises / blockers:** anything unexpected (e.g. the boto3 stream upload reading FileStorage twice and erroring; an admin route that bypasses save_upload; a template that uses a hardcoded `/static/uploads/...` URL string instead of `url_for`).

If anything is genuinely ambiguous (e.g. a template renders a user-upload field via a JS variable not a Jinja variable; an existing route uses `send_file()` to stream from local disk; a model field that turns out to be both upload-derived AND seed-derived under different code paths), STOP and report — DO NOT decide.
