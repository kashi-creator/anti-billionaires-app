"""Null out DB columns whose file no longer exists on disk.

Context: Railway wiped /app/static/uploads on 2026-05-06 and again on
2026-05-08 because no Volume is mounted at the upload path. The DB still
holds paths like "uploads/<uuid>.jpg" that 404 in the browser. This script
finds rows whose path doesn't exist on disk and sets the column to NULL so
templates fall through to the initial-letter / no-image fallback until the
content is re-uploaded.

DRY-RUN BY DEFAULT. Pass --apply to write.

Run on Railway (after the persistent volume is mounted, so any photos that
were already re-uploaded survive):
    railway run sh -c ".venv/bin/python scripts/clear_dead_uploads.py"           # dry run
    railway run sh -c ".venv/bin/python scripts/clear_dead_uploads.py --apply"   # write

Covers every model column populated by save_upload() / _save_upload():
    User.profile_photo
    Post.image_path
    Space.cover_image
    Event.cover_image
    Course.cover_image
    Story.image_path
    Win.image_path
    Deal.image_path
    ChallengeSubmission.image_path
    Reel.thumbnail_path
    Project.cover_image
    ProjectUpdate.image_path
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from app import app, db  # noqa: E402
from models import (  # noqa: E402
    ChallengeSubmission,
    Course,
    Deal,
    Event,
    Post,
    Project,
    ProjectUpdate,
    Reel,
    Space,
    Story,
    User,
    Win,
)

TARGETS = [
    (User, "profile_photo"),
    (Post, "image_path"),
    (Space, "cover_image"),
    (Event, "cover_image"),
    (Course, "cover_image"),
    (Story, "image_path"),
    (Win, "image_path"),
    (Deal, "image_path"),
    (ChallengeSubmission, "image_path"),
    (Reel, "thumbnail_path"),
    (Project, "cover_image"),
    (ProjectUpdate, "image_path"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually write the NULLs.")
    args = parser.parse_args()

    upload_root = app.config["UPLOAD_FOLDER"]
    static_root = os.path.dirname(upload_root)
    print(f"upload_root = {upload_root}")
    print(f"mode = {'APPLY' if args.apply else 'DRY-RUN'}\n")

    with app.app_context():
        grand_total_dead = 0
        grand_total_alive = 0
        for Model, col in TARGETS:
            dead = []
            alive = 0
            rows = Model.query.filter(getattr(Model, col).isnot(None)).all()
            for row in rows:
                rel = getattr(row, col)
                # Stored paths are relative to /static (e.g. "uploads/abc.jpg")
                disk_path = os.path.join(static_root, rel)
                if os.path.isfile(disk_path):
                    alive += 1
                else:
                    dead.append(row)

            grand_total_dead += len(dead)
            grand_total_alive += alive
            print(f"{Model.__name__}.{col}: {len(rows)} rows, {alive} alive, {len(dead)} dead")

            if args.apply and dead:
                for row in dead:
                    setattr(row, col, None)
                db.session.commit()
                print(f"  -> nulled {len(dead)} {Model.__name__}.{col} rows")

        print(f"\ntotal: {grand_total_alive} alive, {grand_total_dead} dead")
        if not args.apply and grand_total_dead:
            print("re-run with --apply to NULL the dead rows.")


if __name__ == "__main__":
    main()
