#!/usr/bin/env python3
"""Append a Sovereign Society Team post to the cron queue.

Three input modes:

    # Single post via stdin:
    echo "Body of the post..." | python scripts/team_post_enqueue.py --space "Sovereign Wealth"

    # Single post from a file:
    python scripts/team_post_enqueue.py --space "Body & Iron" --file path/to/post.txt

    # Bulk (one post per line containing exactly '====='):
    python scripts/team_post_enqueue.py --space "Off Grid" --bulk-file seed_content/off_grid_posts.txt

Bulk skips chunks that are empty after stripping leading '#' comment lines
(matches the seed_content/*.txt format from Phase 12). Posts are appended
to the end of the per-Space queue (queue_position = max + 1). The
daily-cadence cron drains FIFO.

This script only touches the `team_post_queue` table; the `post` table
is untouched. The cron command (`flask cron team-post-publish`) is the
sole writer that promotes queued rows into real Posts.

Production:
    PUBLIC_DB=$(railway variables --service Postgres --json | python3 -c \
        "import json,sys; print(json.load(sys.stdin)['DATABASE_PUBLIC_URL'])")
    railway run sh -c "DATABASE_URL='$PUBLIC_DB' \
        .venv/bin/python scripts/team_post_enqueue.py --space \"Off Grid\" --bulk-file seed_content/off_grid_posts.txt"
"""
import argparse
import os
import re
import sys

# Make repo root importable so we can pull in app + models.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, Space, TeamPostQueue


SEP = re.compile(r"^\s*=====\s*$", re.MULTILINE)


def _clean(raw):
    """Drop leading '#' header lines + trim. Matches seed_content/*.txt format."""
    lines = [l for l in raw.split("\n") if not l.lstrip().startswith("#")]
    return "\n".join(lines).strip()


def enqueue_one(space_name, content):
    """Append a single post to the queue for `space_name`. Returns the new row."""
    space = Space.query.filter_by(name=space_name).first()
    if not space:
        raise SystemExit(f"No Space named {space_name!r}")
    max_pos = (
        db.session.query(db.func.max(TeamPostQueue.queue_position))
        .filter_by(space_id=space.id)
        .scalar()
        or 0
    )
    q = TeamPostQueue(
        space_id=space.id,
        content=content,
        queue_position=max_pos + 1,
        status="pending",
    )
    db.session.add(q)
    db.session.flush()
    return q


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--space", required=True, help="Space name (exact match)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--file", help="Read one post from this file")
    g.add_argument("--bulk-file", help="Read N posts (===== separated) from this file")
    args = p.parse_args()

    with app.app_context():
        if args.bulk_file:
            text = open(args.bulk_file).read()
            posts = [_clean(c) for c in SEP.split(text)]
            posts = [body for body in posts if body]
            if not posts:
                raise SystemExit(f"No posts found in {args.bulk_file!r}")
            for body in posts:
                q = enqueue_one(args.space, body)
                preview = body[:60].replace("\n", " ")
                print(f"  +{q.id} pos={q.queue_position}: {preview!r}")
            print(f"Enqueued {len(posts)} posts to {args.space!r}.")
        else:
            if args.file:
                body = _clean(open(args.file).read())
            else:
                body = _clean(sys.stdin.read())
            if not body:
                raise SystemExit("Empty body.")
            q = enqueue_one(args.space, body)
            preview = body[:70].replace("\n", " ")
            print(f"Enqueued #{q.id} (pos={q.queue_position}) to {args.space!r}: {preview!r}")
        db.session.commit()


if __name__ == "__main__":
    main()
