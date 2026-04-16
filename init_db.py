"""Initialize the database. Run this once to create all tables."""
from app import app
from models import db

with app.app_context():
    db.create_all()
    print("Database initialized successfully.")
