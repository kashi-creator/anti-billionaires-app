#!/usr/bin/env python3
"""
Standalone seed script for Sovereign Society.
Run with: python populate_content.py
Or on Railway: railway run python populate_content.py

This is a convenience wrapper - the same seeding logic runs automatically
on app startup via _seed_content() in app.py.
"""
import os
os.environ.setdefault('SECRET_KEY', 'dev-key')

from app import app, db, _seed_content
from models import User

with app.app_context():
    db.create_all()
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        admin = User.query.first()
    if not admin:
        print("[SEED] No users found in database. Create at least one user first.")
        print("       The seeding will run automatically on next app startup after a user registers.")
    else:
        _seed_content()
        print("[SEED] Done. Content has been seeded.")
