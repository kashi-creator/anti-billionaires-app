# Operations Runbook

## Production cutover checklist (Phase 11)

When you've collected all keys and are ready to go live:

### Required env vars on Railway

```
FLASK_ENV=production
SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=<auto-set by Railway when you attach Postgres>

# Stripe (live mode)
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_ID=price_xxx

# Resend
RESEND_API_KEY=re_xxx
EMAIL_FROM=noreply@yourdomain.com  # must be verified in Resend
EMAIL_FROM_NAME=Sovereign Society

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-4-6
WINGMAN_DAILY_MESSAGE_CAP=50

# Admin
ADMIN_EMAILS=kashi@thebreathcoachschool.com
```

### Stripe setup steps

1. Stripe Dashboard → Products → Create product "Sovereign Society Membership"
2. Add a recurring price: $99/mo
3. Copy the `price_xxx` ID into `STRIPE_PRICE_ID`
4. Stripe Dashboard → Developers → Webhooks → Add endpoint:
   - URL: `https://YOUR-DOMAIN/webhook/stripe`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`
5. Copy the signing secret into `STRIPE_WEBHOOK_SECRET`

### Resend setup steps

1. Resend dashboard → Domains → add your sending domain
2. Add the SPF + DKIM DNS records they show you (typically TXT records on your DNS host)
3. Wait for verification (~5 min)
4. Set `EMAIL_FROM=noreply@yourdomain.com` to a verified address
5. (Optional) Until your domain is verified, you can send from `onboarding@resend.dev`

### Database migration

Railway will run `flask db upgrade` automatically as the release command (configured in `railway.json` and `Procfile`). On first deploy with Postgres, this creates all tables and applies migrations 0–4.

### Smoke test after deploy

```
1. Visit landing → looks right
2. /pricing → enter email → checkout (use test card 4242 4242 4242 4242)
3. After Stripe success: /signup form appears, create password
4. Email arrives with verify link
5. Click verify → "Email confirmed"
6. Land on /onboarding → walk through 5 steps
7. Land on /feed → posts visible
8. /messages → DM another account
9. /wingman → ask the AI a question (verifies Anthropic key works)
10. /admin → see member, click "Grant Lifetime" on a test account
```

### Cutover from test → live Stripe

When ready to take real money:

1. Update STRIPE_* env vars to live keys (`sk_live_`, `pk_live_`)
2. Re-create the product + price in live Stripe (test products don't carry over)
3. Re-create the webhook in live mode (different signing secret)
4. Update `STRIPE_PRICE_ID` and `STRIPE_WEBHOOK_SECRET` in Railway
5. Run a real $99 charge end-to-end with a real card
6. Refund yourself via the admin panel to confirm refund flow

## Common ops actions

### Manually grant lifetime access
- Log into `/admin`, search by email, click into member, "Grant Lifetime"
- Cancels their Stripe sub automatically; future webhooks won't downgrade

### Refund a member
- `/admin/member/<id>` → "Refund Last Payment"
- Or do it directly in Stripe dashboard if it's an older charge

### Comp 30 days
- `/admin/member/<id>` → "Comp 30 Days"
- Sets subscription_status=active, period_end=now+30 days
- Doesn't touch Stripe — purely a DB grant

### Send weekly digest manually
```
flask cron digest
```
Run from Railway's console (`railway run flask cron digest`).

### Send a test email
```
flask cron test-email
```
Sends a "Resend wired up?" test to the first admin user.

### Schedule weekly digest in Railway
1. Railway → New Cron Job
2. Schedule: `0 9 * * 0` (Sundays 9am UTC)
3. Command: `flask cron digest`

### Rotate SECRET_KEY (only if compromised)
- This invalidates all sessions; everyone gets logged out
- Generate new: `python -c "import secrets; print(secrets.token_hex(32))"`
- Update `SECRET_KEY` env var on Railway
- Redeploy

### Lock a member out
- `/admin/member/<id>` → Toggle Subscription (sets to inactive)
- They lose access immediately; can't post, can't message
- Doesn't refund; do that separately if needed

### Reset a forgotten password (admin path)
- Have them use `/forgot-password` directly (the in-app flow)
- If email isn't working, set up a new password by direct DB:
  ```
  flask shell
  >>> from models import User, db
  >>> import bcrypt
  >>> u = User.query.filter_by(email='X').first()
  >>> u.password_hash = bcrypt.hashpw(b'newpassword', bcrypt.gensalt()).decode()
  >>> db.session.commit()
  ```

## Troubleshooting

### "SECRET_KEY must be set in production"
You forgot to set `SECRET_KEY` on Railway. Set it; Railway will auto-redeploy.

### "AI Wingman isn't configured yet"
`ANTHROPIC_API_KEY` not set, set to placeholder, or contains "REPLACE".

### Emails going to spam
Resend domain not verified, or SPF/DKIM records not propagated. Check at Resend dashboard.

### Webhook events not arriving
- Check Stripe dashboard → Webhooks → recent events for delivery failures
- Verify `STRIPE_WEBHOOK_SECRET` matches
- Verify webhook URL is accessible (try GET-ing it; should return 405 method not allowed, not 404)

### Database connection errors under load
Bump `pool_size` and `max_overflow` in [app.py](app.py) `SQLALCHEMY_ENGINE_OPTIONS`. Default is 5+10.

## Backups

Railway Postgres has automatic daily backups (kept 7 days). For longer retention:
```
railway postgres dump > backup-$(date +%Y%m%d).sql
```
