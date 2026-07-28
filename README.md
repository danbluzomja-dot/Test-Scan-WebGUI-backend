# Production Tracker API

A modular Flask backend for tracking manufactured items from a traveler sheet. It
supports badge-based operator attribution, role and application access control,
configurable workflows, QR labels, station scans, QC data, and sensor readings.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app production_tracker:create_app init-db
flask --app production_tracker:create_app seed-demo
flask --app production_tracker:create_app run
```

The demo administrator is `admin` / `change-me` (change it immediately). The
API is JSON-first and uses a signed login session. Set a long random
`SECRET_KEY` and a server database URL (for example PostgreSQL) in production.

## Core flow

1. An administrator creates an application and workflow definition with ordered
   steps (`POST /api/workflows`). Step `form_schema` values describe the fields
   a configurable front end should render; `hardware_schema` describes expected
   instruments or sensors.
2. A permitted user creates a product (`POST /api/products`). The response
   contains an opaque tracking token and QR endpoint.
3. Open `/station` on a phone, tablet, or station PC. Submit the product token,
   station key, and operator badge to
   `POST /api/scans`. The first valid scan starts the current step; scanning it
   again completes it and advances the traveler. Duplicate scanner messages can
   supply an `idempotency_key`.
4. Step form/QC results and sensor readings are supplied in `data` and
   `sensor_data`. Required fields and configured sensor limits are enforced on
   completion. Every transition is retained as an immutable event.
5. Printable travelers contain separate signed next and previous/rework QR
   codes. Rework is restricted to supervisors and administrators.

## API highlights

* `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
* `GET|POST /api/users` (administrator-only user and badge provisioning)
* `GET|POST /api/applications` and `POST /api/applications/<id>/grants`
* `GET|POST /api/workflows`
* `POST /api/workflows/<id>/publish`
* `GET|POST /api/products`, `GET /api/products/<token>`
* `GET /api/products/<token>/qr` (PNG) and `/traveler` (printable PDF)
* `POST /api/scans` and `GET /api/products/<token>/events`

The included responsive station console supports keyboard-style scanners and
browser camera QR scanning where the `BarcodeDetector` API is available.

See [`docs/API.md`](docs/API.md) for request examples and the workflow schema.

## Design notes

QR codes contain only an opaque random product token, not employee or product
details. Badge values are also stored as keyed hashes. Deploy behind HTTPS,
rotate secrets, use a production database, and connect authentication to your
organization's identity provider before handling real production data.

Run tests with `pytest`.
