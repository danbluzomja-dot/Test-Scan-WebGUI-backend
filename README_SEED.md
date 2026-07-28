## Seeding the database (demo)

To make the demo immediately usable there's a seeding command and a convenience script.

- Using Flask CLI (recommended if you want to run within Flask's command system):

  1. Ensure FLASK_APP is set to the run module:
     - For bash: export FLASK_APP=run
     - For Windows (Powershell): $env:FLASK_APP = "run"

  2. Run the seed command (this requires the app context):
     flask seed-data

- Using the convenience script:

  Just run the script which will create tables (db.create_all()) if needed and insert seed data:

    python scripts/seed.py

Seeded items:
- Roles: operator, supervisor
- User: admin (badge_id: ADMIN123, password: changeme)
- ProcessTemplate: "Sample Process" with a few steps
- Product: barcode PROD0001 linked to the sample process

After seeding you can login on the demo page using badge ADMIN123 (no password needed for badge login),
then enter PROD0001 as the product barcode to test start/complete/traveler flows.
