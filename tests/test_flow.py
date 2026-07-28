import pytest

from production_tracker import create_app
from production_tracker.api import badge_digest
from production_tracker.api import action_token, validate_step_payload
from production_tracker.extensions import db
from production_tracker.models import Application, User, Workflow


@pytest.fixture()
def app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "BADGE_HASH_KEY": "test-badge", "SQLALCHEMY_DATABASE_URI": "sqlite://"})
    with app.app_context():
        db.create_all()
        application = Application(key="line", name="Line")
        user = User(username="op", role="admin", badge_hash=badge_digest("B-1")); user.set_password("password")
        user.applications.append(application)
        workflow = Workflow(application=application, name="Build", published=True, definition={"steps": [
            {"key": "build", "name": "Build", "station_key": "S-1"},
            {"key": "qc", "name": "QC", "station_key": "S-2"},
        ]})
        db.session.add_all([application, user, workflow]); db.session.commit()
    yield app


@pytest.fixture()
def client(app): return app.test_client()


def login(client):
    assert client.post("/api/auth/login", json={"username": "op", "password": "password"}).status_code == 200


def test_complete_workflow_and_reject_wrong_station(client):
    login(client)
    product = client.post("/api/products", json={"workflow_id": 1, "serial_number": "SN-1"}).get_json()
    token = product["token"]
    assert client.post("/api/scans", json={"product_token": token, "badge": "B-1", "station_key": "bad"}).status_code == 409
    first = client.post("/api/scans", json={"product_token": token, "badge": "B-1", "station_key": "S-1", "idempotency_key": "1"})
    assert first.get_json()["action"] == "start"
    duplicate = client.post("/api/scans", json={"product_token": token, "badge": "B-1", "station_key": "S-1", "idempotency_key": "1"})
    assert duplicate.get_json()["duplicate"] is True
    assert client.post("/api/scans", json={"product_token": token, "badge": "B-1", "station_key": "S-1"}).get_json()["action"] == "complete"
    client.post("/api/scans", json={"product_token": token, "badge": "B-1", "station_key": "S-2"})
    done = client.post("/api/scans", json={"product_token": token, "badge": "B-1", "station_key": "S-2"}).get_json()
    assert done["status"] == "complete"
    assert len(client.get(f"/api/products/{token}/events").get_json()) == 4


def test_qr_and_traveler(client):
    login(client)
    token = client.post("/api/products", json={"workflow_id": 1, "serial_number": "SN-2"}).get_json()["token"]
    assert client.get(f"/api/products/{token}/qr").mimetype == "image/png"
    assert client.get(f"/api/products/{token}/traveler").mimetype == "application/pdf"


def test_schema_validation_and_rework(app, client):
    assert validate_step_payload(
        {"form_schema": {"passed": {"type": "boolean", "required": True}},
         "hardware_schema": {"torque": {"min": 8, "max": 10}}},
        {}, {"torque": 12},
    ) == {"passed": "is required", "sensor_data.torque": "is outside the permitted range"}
    login(client)
    product = client.post("/api/products", json={"workflow_id": 1, "serial_number": "SN-3"}).get_json()
    client.post("/api/scans", json={"product_token": product["token"], "badge": "B-1", "station_key": "S-1"})
    client.post("/api/scans", json={"product_token": product["token"], "badge": "B-1", "station_key": "S-1"})
    with app.app_context():
        from production_tracker.models import Product
        token = action_token(Product.query.filter_by(token=product["token"]).one(), "previous")
    response = client.post("/api/scans", json={"action_token": token, "badge": "B-1", "station_key": "S-2"})
    assert response.get_json()["action"] == "rework"
    assert response.get_json()["current_step"] == 0
