"""Seed script for development convenience.

This script will create the database tables (using db.create_all()) if they do not exist
and then insert the demo seed data. Run this once after installing dependencies and
configuring DATABASE_URL (or rely on the default sqlite dev.db).

Usage:
    python scripts/seed.py

"""
from app import create_app, db
from app.cli import do_seed

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # create tables if migrations have not been run
        db.create_all()
        do_seed()
        print('Seeding complete.')
