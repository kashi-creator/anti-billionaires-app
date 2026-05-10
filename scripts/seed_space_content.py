"""
seed_space_content.py — Phase 12 (Sovereign Society)

Two modes:

    generate
        Calls Anthropic to write 15 starter posts per Space, matching the
        voice + format of the hand-written Off Grid posts. Saves each Space
        to its own file under seed_content/<slug>_posts.txt. Does NOT touch
        the DB. Re-runnable; overwrites previously generated files.

    insert
        Reads seed_content/<slug>_posts.txt, splits on "=====", and inserts
        each post directly via SQLAlchemy. Bypasses route-level side effects
        (no points awards, no checklist auto-checks, no notifications, no
        GHL pushes). Round-robin author across active members. created_at
        staggered randomly across the past 21 days. Idempotent on
        title-prefix match — re-runs skip already-inserted posts.

Usage:
    python scripts/seed_space_content.py generate --space "Sovereign Wealth"
    python scripts/seed_space_content.py generate --all
    python scripts/seed_space_content.py insert   --space "Off Grid"
    python scripts/seed_space_content.py insert   --all

Production:
    PUBLIC_DB=$(railway variables --service Postgres --json | python3 -c \
        "import json,sys; print(json.load(sys.stdin)['DATABASE_PUBLIC_URL'])")
    railway run sh -c "DATABASE_URL='$PUBLIC_DB' \
        .venv/bin/python scripts/seed_space_content.py generate --all"
    railway run sh -c "DATABASE_URL='$PUBLIC_DB' \
        .venv/bin/python scripts/seed_space_content.py insert --all"
"""

import argparse
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Make repo root importable so we can pull in app + models.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SEED_DIR = REPO_ROOT / "seed_content"
OFF_GRID_FILE = SEED_DIR / "off_grid_posts.txt"

# DB names match the live schema (post-rename: Brotherhood Ops → Business
# Directory, Red Pill Intel → The Hidden Truth — see app.py:441).
SPACES = [
    {
        "name": "Sovereign Wealth",
        "slug": "sovereign_wealth",
        "theme": (
            "Capital allocation, macro thinking, deal flow, building income "
            "streams, real estate, asset protection, taxes, and getting "
            "money out of the rigged casino into real assets. Builder-tone, "
            "practical, not financial-advisor cliche."
        ),
        "title_examples": [
            "How To Think About Cash Flow Before Net Worth",
            "How To Find Off-Market Deals When You Don't Know Anyone",
            "How To Start Building a Real Estate Portfolio With Limited Capital",
        ],
    },
    {
        "name": "Body & Iron",
        "slug": "body_iron",
        "theme": (
            "Strength, training discipline, recovery, masculine fitness "
            "identity, nutrition without trends, longevity. Operator-tone. "
            "Cutting the poison out of food. Not bro-science. Real food, "
            "real training, real results."
        ),
        "title_examples": [
            "How To Train Through Decades, Not Months",
            "How To Build Discipline When Motivation Disappears",
            "How To Eat Like a Man Who Has Things to Do",
        ],
    },
    {
        "name": "Awake Minds",
        "slug": "awake_minds",
        "theme": (
            "Suppressed knowledge, consciousness, contrarian frameworks, "
            "questioning systemic narratives, mental models, our place in "
            "the cosmos. Direct, not paranoid. Question everything, accept "
            "nothing at face value."
        ),
        "title_examples": [
            "How To Read in a Way That Actually Changes You",
            "How To Think Independently in a Connected World",
            "How To Audit Your Own Beliefs Without Losing Your Footing",
        ],
    },
    {
        "name": "Business Directory",
        "slug": "business_directory",
        "theme": (
            "Supporting each other's businesses, referrals, accountability "
            "between sovereign men who run companies. How to ask for help, "
            "how to vet a brother before recommending him, how to build "
            "trust-based deal flow inside the brotherhood. Action-tone. "
            "We rise together or not at all."
        ),
        "title_examples": [
            "How To Ask The Brotherhood For A Referral Without Being Awkward",
            "How To Vet A Brother Before Sending Him Business",
            "How To Show Up For Another Man's Business Without Being Asked",
        ],
    },
    {
        "name": "The Arsenal",
        "slug": "arsenal",
        "theme": (
            "2A discussion, preparedness, self-defense, EDC, home defense, "
            "personal sovereignty hardware, training, mindset. The ultimate "
            "safeguard of a free people. Practical, opinionated, grounded "
            "in real training, not gun-store mall-ninja talk."
        ),
        "title_examples": [
            "How To Choose Your First Carry Pistol Without Overthinking It",
            "How To Train So You Actually Trust Yourself Under Stress",
            "How To Set Up A Home Defense Plan Your Wife Knows By Heart",
        ],
    },
    {
        "name": "The Hidden Truth",
        "slug": "hidden_truth",
        "theme": (
            "Elite corruption, trafficking, media manipulation, what the "
            "powerful do not want seen, signal versus noise. Calm, direct, "
            "evidence-aware. Not conspiracy-flavored ranting — the kind of "
            "writing a man does after he has actually done the reading. "
            "Drag the truth into the light."
        ),
        "title_examples": [
            "How To Filter Modern News Without Becoming Cynical",
            "How To Spot Manufactured Consensus",
            "How To Read Between The Lines Of Government Statistics",
        ],
    },
    {
        "name": "Family & Legacy",
        "slug": "family_legacy",
        "theme": (
            "Fatherhood, marriage, raising sovereign children, building for "
            "your sons, protecting your bloodline, generational wealth. "
            "Earnest, not sentimental. What you build must outlast you."
        ),
        "title_examples": [
            "How To Be A Father Your Sons Want To Become",
            "How To Build A Family That Outlasts You",
            "How To Have Hard Conversations With Your Children",
        ],
    },
    # Off Grid — hand-written by Kashi at seed_content/off_grid_posts.txt.
    # Listed here so `insert --all` covers it; never sent to AI generation.
    {
        "name": "Off Grid",
        "slug": "off_grid",
        "theme": "(hand-written by Kashi — see seed_content/off_grid_posts.txt)",
        "title_examples": [],
    },
]

SPACES_BY_NAME = {s["name"]: s for s in SPACES}
SPACES_BY_SLUG = {s["slug"]: s for s in SPACES}

# Off Grid is hand-written by Kashi, never AI-generated.
OFF_GRID_NAME = "Off Grid"
GENERATED_SPACES = [s for s in SPACES if s["name"] != "Off Grid"]

BANNED_PHRASES = [
    "delve into",
    "dive in",
    "let's explore",
    "let us explore",
    "it's worth noting",
    "it is worth noting",
    "in today's world",
    "at the end of the day",
    "unleash",
    "journey of",
    "embrace",
    "harness",
    "tapestry",
    "realm",
    "master the art",
]

MIN_WORDS = 80
MAX_WORDS = 400
POSTS_PER_SPACE = 15
MAX_PROMPT_RETRIES = 2

# Voice anchor — manifesto block from templates/landing.html lines 589-593.
MANIFESTO = """We are living in an engineered reality.

The food is poisoned. The money is fake. History is sanitized. And our men
are weak. The architects of this system do not want you strong, sovereign,
or awake.

They want you medicated. Dependent. Distracted. We refuse the terms of this
surrender.

This is not a political movement. It is a reclamation of masculine power.
A brotherhood of builders, thinkers, and protectors who chose to step out
of the chaos and into purpose. We do not just complain about the dark.
We build the fire."""

MODEL = os.environ.get("SEED_CONTENT_MODEL", "claude-sonnet-4-6")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("seed_space_content")


def _load_off_grid_examples(n=3):
    """Pull the first n posts out of off_grid_posts.txt as voice exemplars."""
    if not OFF_GRID_FILE.exists():
        raise SystemExit(f"missing {OFF_GRID_FILE}")
    raw = OFF_GRID_FILE.read_text()
    chunks = [c.strip() for c in raw.split("=====")]
    # Skip the leading comment block — first real post starts at "How To Start..."
    posts = []
    for c in chunks:
        body_lines = [ln for ln in c.splitlines() if not ln.startswith("#")]
        body = "\n".join(body_lines).strip()
        if body and not body.startswith("#"):
            posts.append(body)
        if len(posts) == n:
            break
    return posts


def _build_system_prompt(off_grid_examples):
    """The cacheable prefix — voice anchor + format rules + 3 Off Grid posts."""
    examples_block = "\n\n=====\n\n".join(off_grid_examples)
    return f"""You are writing starter posts for the private community Sovereign Society — an application-only brotherhood of operators, builders, and protectors. Your writing must match the founder's voice exactly.

VOICE ANCHOR (the manifesto — match this tone exactly):

{MANIFESTO}

CONTENT EXAMPLES (the format and density to match — these were written by the founder Kashi for the Off Grid Space, and represent the voice/format canon):

=====

{examples_block}

=====

FORMAT RULES — every post MUST match exactly:
- Line 1: the title, no markdown emphasis (no asterisks, no hashes)
- Line 2: blank
- Lines 3+: body — short paragraphs (1-3 sentences), structured bullet lists where appropriate using the bullet character (U+2022)
- 100-300 words per post
- Direct, declarative, builder-tone
- NO em-dashes anywhere (use periods or commas instead)
- NO exclamation points
- NO hashtags
- NO emojis
- NO numbered lists (use the bullet character for lists)
- NO meta-language like "Here are the posts" or "Post 1:"

BANNED PHRASES — these MUST NOT appear in any post (case-insensitive):
{', '.join(BANNED_PHRASES)}

OUTPUT FORMAT:
Output exactly 15 standalone posts, separated by lines containing exactly "=====" (5 equals signs, nothing else on that line).

Do not number the posts. Do not add a preamble. Do not add commentary between posts. Do not summarize at the end. Just the 15 posts separated by ===== lines.
"""


def _build_user_prompt(space):
    return f"""Write 15 starter posts for the "{space['name']}" Space.

Theme for {space['name']}:
{space['theme']}

For variety, the 15 posts should cover a mix of practical how-to, mindset, common mistakes, and tactical specifics. Examples of titles in scope (do NOT copy these verbatim — use them as a sense of the bandwidth):
{chr(10).join('- ' + t for t in space['title_examples'])}

Generate 15 distinct posts now. Output the 15 posts separated by ===== lines."""


def _validate_post(text):
    """Return None if valid, else a string describing the rejection reason."""
    text = text.strip()
    if not text:
        return "empty"
    if "—" in text or "–" in text:
        return "em-dash present"
    if "!" in text:
        return "exclamation point present"
    lower = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lower:
            return f"banned phrase: {phrase!r}"
    word_count = len(text.split())
    if word_count < MIN_WORDS:
        return f"too short ({word_count} words)"
    if word_count > MAX_WORDS:
        return f"too long ({word_count} words)"
    return None


def _split_response(raw):
    return [p.strip() for p in raw.split("=====") if p.strip()]


def _generate_for_space(client, space, off_grid_examples):
    """Returns a list of 15 validated post strings (or fewer on persistent failure)."""
    system_prompt = _build_system_prompt(off_grid_examples)
    user_prompt = _build_user_prompt(space)

    accepted = []
    attempts = 0
    while attempts <= MAX_PROMPT_RETRIES and len(accepted) < POSTS_PER_SPACE:
        attempts += 1
        log.info(
            "[%s] attempt %d — calling %s (have %d/%d valid posts)",
            space["slug"], attempts, MODEL, len(accepted), POSTS_PER_SPACE,
        )
        # Cache the system prompt — same across all 7 Spaces, ~3K+ tokens.
        msg = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
        )

        usage = getattr(msg, "usage", None)
        if usage:
            log.info(
                "[%s] usage: input=%d cache_read=%d cache_create=%d output=%d",
                space["slug"],
                getattr(usage, "input_tokens", 0),
                getattr(usage, "cache_read_input_tokens", 0),
                getattr(usage, "cache_creation_input_tokens", 0),
                getattr(usage, "output_tokens", 0),
            )

        text = "".join(
            b.text for b in msg.content if getattr(b, "type", None) == "text"
        )
        candidates = _split_response(text)
        log.info("[%s] received %d candidate posts", space["slug"], len(candidates))

        for c in candidates:
            if len(accepted) >= POSTS_PER_SPACE:
                break
            reason = _validate_post(c)
            if reason is None:
                accepted.append(c)
            else:
                preview = c.splitlines()[0][:60] if c else "<empty>"
                log.warning(
                    "[%s] rejected (%s): %s", space["slug"], reason, preview,
                )

        if len(accepted) < POSTS_PER_SPACE:
            log.info(
                "[%s] %d/%d accepted, retrying",
                space["slug"], len(accepted), POSTS_PER_SPACE,
            )

    return accepted


def _write_posts_file(space, posts):
    SEED_DIR.mkdir(exist_ok=True)
    path = SEED_DIR / f"{space['slug']}_posts.txt"
    header = (
        f"# {space['name']} space — {len(posts)} starter posts (AI-generated, "
        f"Phase 12)\n"
        f"# Format: each post separated by a line of \"=====\". "
        f"First line of each post is the title.\n"
        f"# Body follows. Voice anchor: manifesto block from "
        f"templates/landing.html.\n"
        f"# Generated against Kashi-written Off Grid examples.\n\n"
    )
    body = "\n=====\n".join(posts) + "\n"
    path.write_text(header + body)
    log.info("[%s] wrote %d posts to %s (%d bytes)",
             space["slug"], len(posts), path, path.stat().st_size)
    return path


def cmd_generate(args):
    try:
        import anthropic
    except ImportError:
        raise SystemExit("anthropic not installed — pip install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set")

    off_grid_examples = _load_off_grid_examples(n=3)
    client = anthropic.Anthropic()

    if args.all:
        targets = GENERATED_SPACES
    else:
        space = SPACES_BY_NAME.get(args.space)
        if not space:
            raise SystemExit(
                f"unknown space {args.space!r} — must be one of: "
                f"{', '.join(s['name'] for s in GENERATED_SPACES)}"
            )
        if space["name"] == OFF_GRID_NAME:
            raise SystemExit(
                "Off Grid is hand-written — generate is not run for that Space"
            )
        targets = [space]

    for i, space in enumerate(targets):
        log.info("=" * 60)
        log.info("Generating: %s (%d/%d)", space["name"], i + 1, len(targets))
        log.info("=" * 60)
        posts = _generate_for_space(client, space, off_grid_examples)
        if not posts:
            log.error("[%s] generation failed entirely", space["slug"])
            continue
        _write_posts_file(space, posts)
        # Polite cushion between Space generations to avoid burst rate limits.
        if i < len(targets) - 1:
            time.sleep(1)


def _active_member_query():
    """Active = subscribed/lifetime/admin AND not a Phase 0B placeholder."""
    from models import User
    from sqlalchemy import or_, not_
    return (
        User.query
        .filter(
            or_(
                User.is_admin == True,  # noqa: E712
                User.lifetime_access == True,  # noqa: E712
                User.subscription_status.in_(["active", "trialing"]),
            )
        )
        .filter(not_(User.email.like("%@sovereign.placeholder")))
    )


def cmd_insert(args):
    from app import app, db
    from models import Post, Space

    if args.all:
        targets = SPACES
    else:
        space = SPACES_BY_NAME.get(args.space)
        if not space:
            raise SystemExit(
                f"unknown space {args.space!r} — must be one of: "
                f"{', '.join(s['name'] for s in SPACES)}"
            )
        targets = [space]

    with app.app_context():
        active_members = _active_member_query().all()
        if not active_members:
            raise SystemExit(
                "no active members found — cannot attribute seed posts"
            )
        log.info("active members for attribution: %d", len(active_members))
        for u in active_members:
            log.info("  - %s (%s)", u.email, u.name or "?")

        total_inserted = 0
        total_skipped = 0
        for space_def in targets:
            path = SEED_DIR / f"{space_def['slug']}_posts.txt"
            if not path.exists():
                log.warning("[%s] %s missing — skip", space_def["slug"], path)
                continue
            inserted, skipped = _insert_from_file(
                space_def, path, db, Post, Space, active_members,
            )
            total_inserted += inserted
            total_skipped += skipped
        log.info(
            "DONE — inserted %d, skipped (already existed) %d",
            total_inserted, total_skipped,
        )


def _strip_header_comments(raw):
    """Drop leading lines that start with '#'. Returns trimmed text."""
    lines = raw.splitlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("#")):
        lines.pop(0)
    return "\n".join(lines)


def _insert_from_file(space_def, path, db, Post, Space, active_members):
    space = Space.query.filter_by(name=space_def["name"]).first()
    if not space:
        log.error("[%s] Space %r not in DB — skip",
                  space_def["slug"], space_def["name"])
        return (0, 0)

    raw = path.read_text()
    raw = _strip_header_comments(raw)
    chunks = [c.strip() for c in raw.split("=====") if c.strip()]

    inserted = 0
    skipped = 0
    for i, body in enumerate(chunks):
        title = body.splitlines()[0].strip() if body else ""
        if not title:
            continue
        # Idempotency: skip if a post with this title prefix already exists.
        existing = (
            Post.query
            .filter_by(space_id=space.id)
            .filter(Post.content.startswith(title))
            .first()
        )
        if existing:
            skipped += 1
            continue
        author = active_members[i % len(active_members)]
        ts = datetime.utcnow() - timedelta(
            days=random.randint(0, 21),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        post = Post(
            user_id=author.id,
            space_id=space.id,
            content=body,
            created_at=ts,
            updated_at=ts,
        )
        db.session.add(post)
        inserted += 1

    db.session.commit()
    log.info(
        "[%s] inserted %d, skipped %d", space_def["slug"], inserted, skipped,
    )
    return (inserted, skipped)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_gen = sub.add_parser("generate", help="Call Anthropic, write per-Space files")
    g = p_gen.add_mutually_exclusive_group(required=True)
    g.add_argument("--space", help="Single space name (e.g. \"Sovereign Wealth\")")
    g.add_argument("--all", action="store_true", help="All 7 non-Off-Grid spaces")
    p_gen.set_defaults(func=cmd_generate)

    p_ins = sub.add_parser("insert", help="Insert per-Space files into DB")
    g2 = p_ins.add_mutually_exclusive_group(required=True)
    g2.add_argument("--space", help="Single space name")
    g2.add_argument("--all", action="store_true", help="All 8 spaces (incl. Off Grid)")
    p_ins.set_defaults(func=cmd_insert)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
