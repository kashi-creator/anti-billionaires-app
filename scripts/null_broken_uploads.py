"""Null out User.profile_photo paths whose R2 key (or local file) doesn't exist.

Run after Phase 9 ships so the 5 users with broken paths from Railway's
ephemeral-disk era get clean placeholders + can re-upload.

Usage:
    railway run python scripts/null_broken_uploads.py
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
