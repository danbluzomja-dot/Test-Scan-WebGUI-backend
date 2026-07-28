# Test-Scan-WebGUI-backend

Backend scaffold for the Test-Scan Web GUI production tracking system.

This repository contains a minimal Flask backend using the pinned packages in requirements.txt. It provides:
- SQLAlchemy models for Users, Roles, ProcessTemplates, Products, and TravelerLogs
- Simple authentication (badge-based login using Flask-Login)
- API endpoints to fetch product state and to start/complete steps
- QR code generation endpoint (PNG)
- Simple traveler PDF generation endpoint
- SocketIO integration for future realtime updates

Getting started (development):

1. Create a virtual environment
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows

2. Install dependencies
   pip install -r requirements.txt

3. Create environment variables (optional)
   - DATABASE_URL (defaults to sqlite:///dev.db)
   - SECRET_KEY (defaults to 'dev' if not set)

4. Initialize the database and run migrations
   flask db init
   flask db migrate -m "initial"
   flask db upgrade

5. Run the app (development)
   python run.py

Notes and next steps
- This is an initial scaffold. The models and routes are intentionally minimal and meant to be expanded.
- The SocketIO server currently runs with the default async mode; for production real-time support add an async worker (eventlet/gevent) and a message queue for scaling.
- The frontend demo (frontend/index.html) is a very small example showing how to call the API; replace it with a SPA later.

