# Sovereign Society

Custom Skool-like community platform for sovereign men — networking, accountability, and deal flow.

> **Naming history:** Originally "Anti Billionaires Men's Club" → "The 1% Men's Club" → renamed to **Sovereign Society**. The repo path (`anti-billionaires-app`), GitHub remote, Capacitor bundle ID (`com.onepercentmensclub.app`), and Railway URL still reference legacy names — these are infrastructure-tied and intentionally not renamed.

## Stack
- **Backend:** Flask + SQLAlchemy (Python)
- **Database:** SQLite (43 tables)
- **Frontend:** Jinja2 templates, vanilla JS, Leaflet.js (maps)
- **Deploy:** Railway + GitHub (`kashi-creator/anti-billionaires-app`)
- **Design:** Gold (#D4AF37) on black (#0A0A0A), luxury aesthetic
- **Landing page:** Standalone full-bleed cinematic page (does NOT extend `base.html`). Fonts: Fraunces (serif), Inter (body), JetBrains Mono (HUD). Effects: vanilla `<canvas>` gold-rain, IntersectionObserver fade-ins, fixed HUD nav with active-chapter tracking, FAQ accordion. No external JS libs.

## Architecture

```
app.py              # Main Flask app, blueprint registration, migrations, error handlers
models.py           # SQLAlchemy models (43 tables), User model with tiers/levels
features_routes.py  # All feature routes (26 features, 650+ lines)
phase3_routes.py    # Layer 3 polish routes
init_db.py          # Database initialization
populate_content.py # Content seeding
static/             # CSS, JS, images
templates/          # Jinja2 templates (29+ feature templates, 3 error templates)
instance/           # SQLite database
```

## Features (26 total)

### Core Social
- Direct Messages (polling-based real-time chat)
- Stories (24hr expiry, story strip on feed)
- Member Tiers (bronze/silver/gold/platinum - computed)
- Leveling System (Level 1-10 with titles - computed)
- Wins Wall (emoji reactions: fire, muscle, crown, clap, rocket)
- Deal Board (7 categories, interest tracking)

### Engagement
- Weekly Challenges (submissions, voting, points)
- Member Spotlights (top 5 by points)
- Resource Vault (8 categories, upvoting)
- Referral System (unique codes, session tracking)
- Accountability (goals, pairs, check-ins)
- Post Bookmarks (AJAX toggle)
- Badges/Achievements (7 default badges)

### Advanced
- Reels (YouTube/Vimeo embed)
- Space Chat (polling-based real-time)
- AI Wingman (placeholder when no API key)
- Member Map (Leaflet.js dark theme)
- Call Booking (request/confirm/cancel)
- Virtual Boardroom (gated to Platinum/Level 9+)

### Polish
- Empty states, custom error pages (404/500/403), mobile tab bar
- Security headers, flash auto-dismiss, activity feed, full-text search

## Community Spaces (seeded)
1. The Vault - exclusive deals & opportunities
2. Business Strategy Room - tactics & growth
3. Networking Lounge - connections & collabs
4. Investment Club - portfolio & markets
5. Wellness & Health - optimization
6. Creator's Corner - content & brand

## Recurring Events (seeded)
- Weekly Mastermind Call, Monthly Networking Mixer, Guest Speaker sessions
- Deal Flow Friday, Wellness Workshops

## Commands

```bash
# Run locally
pip install -r requirements.txt
python app.py

# Deploy
git push origin main  # Railway auto-deploys from GitHub

# Seed content
python populate_content.py
python init_db.py
```

## Design Rules
- All UI must maintain the gold (#D4AF37) + black (#0A0A0A) luxury aesthetic
- Manus-level premium feel: serif fonts, massive spacing, subtle animations
- Mobile-first with fixed bottom tab bar (Feed, Messages, Wins, Search, Profile)
