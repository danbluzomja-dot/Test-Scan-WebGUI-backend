# API examples

All endpoints except health and login require the signed login cookie. Roles are
`operator`, `supervisor`, `engineer`, and `admin`. Administrators see every
application; all other users must have an explicit application grant.

Administrators provision accounts and badge mappings with `POST /api/users`.
The submitted badge is converted to a keyed hash and is never returned by the
API. An account can be assigned to one or more applications at creation time by
including `application_ids`.

## Workflow definition

```json
{
  "application_id": 1,
  "name": "Pump assembly",
  "version": 1,
  "definition": {
    "steps": [{
      "key": "torque-housing",
      "name": "Torque housing",
      "station_key": "TORQUE-01",
      "form_schema": {
        "visual_pass": {"type": "boolean", "required": true},
        "notes": {"type": "text"}
      },
      "hardware_schema": {"torque": {"unit": "Nm", "min": 8, "max": 10}}
    }]
  }
}
```

Schemas are deliberately stored as data so a front end can render new tasks and
QC inputs without a code deployment. Workflow versions should be immutable once
products use them; publish a new version for future products with
`POST /api/workflows/<id>/publish`. Products can only be created from published
workflows. Required form values, numeric sensor values, and configured minimum
and maximum limits are enforced when a step is completed.

## Scan

```http
POST /api/scans
Content-Type: application/json

{
  "product_token": "token-from-product-qr",
  "badge": "raw-value-from-employee-badge",
  "station_key": "TORQUE-01",
  "idempotency_key": "scanner-message-uuid",
  "data": {"visual_pass": true},
  "sensor_data": {"torque": 9.2}
}
```

The badge identifies the employee who performed the work; the logged-in user
identifies the authorized terminal session. The first scan records `start`; the
second records `complete` and selects the next configured step. An idempotency
key makes scanner retries safe.

The traveler PDF contains signed `next` and `previous` action tokens. A station
may send `action_token` instead of `product_token`; altered tokens are rejected.
The previous action creates an auditable `rework` event and requires the logged-
in session user to be a supervisor or administrator.
