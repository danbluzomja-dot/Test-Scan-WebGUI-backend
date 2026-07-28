import hashlib
import hmac
import io
import secrets

import qrcode
from flask import Blueprint, current_app, jsonify, request, send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.orm.exc import StaleDataError

from .auth import current_user, login_required, roles_required
from .extensions import db
from .models import Application, ProcessEvent, Product, User, Workflow, utcnow

bp = Blueprint("api", __name__, url_prefix="/api")
VALID_ROLES = {"operator", "supervisor", "engineer", "admin"}


def badge_digest(value):
    return hmac.new(current_app.config["BADGE_HASH_KEY"].encode(), value.encode(), hashlib.sha256).hexdigest()


def can_access(user, application):
    return application.active and (user.role == "admin" or application in user.applications)


def action_token(product, action):
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="traveler-action").dumps(
        {"product": product.token, "action": action}
    )


def decode_action_token(value):
    try:
        return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="traveler-action").loads(value)
    except BadSignature:
        return None


def validate_step_payload(step, data, sensor_data):
    """Validate configurable inputs without coupling the API to a specific line."""
    errors = {}
    type_map = {"text": str, "number": (int, float), "boolean": bool, "integer": int}
    for name, rule in step.get("form_schema", {}).items():
        value = data.get(name)
        if rule.get("required") and value is None:
            errors[name] = "is required"
        elif (value is not None and rule.get("type") in type_map
              and (not isinstance(value, type_map[rule["type"]])
                   or rule["type"] in ("number", "integer") and isinstance(value, bool))):
            errors[name] = f"must be {rule['type']}"
    for name, rule in step.get("hardware_schema", {}).items():
        value = sensor_data.get(name)
        if rule.get("required", True) and value is None:
            errors[f"sensor_data.{name}"] = "is required"
        elif value is not None and not isinstance(value, (int, float)):
            errors[f"sensor_data.{name}"] = "must be numeric"
        elif value is not None and (value < rule.get("min", value) or value > rule.get("max", value)):
            errors[f"sensor_data.{name}"] = "is outside the permitted range"
    return errors


def product_json(product):
    steps = product.workflow.definition["steps"]
    return {"token": product.token, "serial_number": product.serial_number,
            "status": product.status, "current_step": product.current_step,
            "step": steps[product.current_step] if product.current_step < len(steps) else None,
            "workflow": {"id": product.workflow.id, "name": product.workflow.name,
                         "version": product.workflow.version}}


@bp.route("/users", methods=["GET", "POST"])
@roles_required("admin")
def users():
    if request.method == "GET":
        return jsonify([{"id": user.id, "username": user.username, "role": user.role,
                         "active": user.active, "applications": [app.key for app in user.applications]}
                        for user in User.query.order_by(User.username)])
    body = request.get_json() or {}
    if (not body.get("username") or not body.get("password") or not body.get("badge")
            or body.get("role", "operator") not in VALID_ROLES):
        return jsonify(error="username, password, badge, and a valid role are required"), 400
    user = User(username=body["username"], role=body.get("role", "operator"),
                badge_hash=badge_digest(str(body["badge"])))
    user.set_password(body["password"])
    app_ids = body.get("application_ids", [])
    user.applications = list(Application.query.filter(Application.id.in_(app_ids))) if app_ids else []
    db.session.add(user)
    db.session.commit()
    return jsonify(id=user.id, username=user.username, role=user.role), 201


@bp.get("/applications")
@login_required
def applications():
    user = current_user()
    rows = Application.query.all() if user.role == "admin" else user.applications
    return jsonify([{"id": row.id, "key": row.key, "name": row.name, "logo_url": row.logo_url} for row in rows])


@bp.post("/applications")
@roles_required("admin")
def create_application():
    body = request.get_json() or {}
    if not body.get("key") or not body.get("name"):
        return jsonify(error="key and name are required"), 400
    row = Application(key=body["key"], name=body["name"], logo_url=body.get("logo_url"))
    db.session.add(row); db.session.commit()
    return jsonify(id=row.id, key=row.key, name=row.name), 201


@bp.post("/applications/<int:application_id>/grants")
@roles_required("admin")
def grant(application_id):
    app = db.get_or_404(Application, application_id)
    user = db.get_or_404(User, (request.get_json() or {}).get("user_id"))
    if app not in user.applications:
        user.applications.append(app); db.session.commit()
    return "", 204


@bp.route("/workflows", methods=["GET", "POST"])
@login_required
def workflows():
    user = current_user()
    if request.method == "GET":
        rows = Workflow.query.all()
        return jsonify([{"id": w.id, "name": w.name, "version": w.version, "definition": w.definition}
                        for w in rows if can_access(user, w.application)])
    if user.role not in ("admin", "engineer"):
        return jsonify(error="insufficient access"), 403
    body = request.get_json() or {}
    app = db.session.get(Application, body.get("application_id"))
    definition = body.get("definition", {})
    if not app or not can_access(user, app) or not isinstance(definition.get("steps"), list) or not definition["steps"]:
        return jsonify(error="accessible application and non-empty definition.steps are required"), 400
    required = {"key", "name", "station_key"}
    if any(not required.issubset(step) for step in definition["steps"]):
        return jsonify(error="each step requires key, name, and station_key"), 400
    row = Workflow(application=app, name=body.get("name", "Workflow"),
                   version=body.get("version", 1), definition=definition)
    db.session.add(row); db.session.commit()
    return jsonify(id=row.id), 201


@bp.post("/workflows/<int:workflow_id>/publish")
@roles_required("admin", "engineer")
def publish_workflow(workflow_id):
    workflow = db.get_or_404(Workflow, workflow_id)
    if not can_access(current_user(), workflow.application):
        return jsonify(error="insufficient access"), 403
    workflow.published = True
    db.session.commit()
    return jsonify(id=workflow.id, published=True)


@bp.route("/products", methods=["GET", "POST"])
@login_required
def products():
    user = current_user()
    if request.method == "GET":
        return jsonify([product_json(p) for p in Product.query.all() if can_access(user, p.workflow.application)])
    body = request.get_json() or {}
    workflow = db.session.get(Workflow, body.get("workflow_id"))
    if not workflow or not workflow.active or not workflow.published or not can_access(user, workflow.application) or not body.get("serial_number"):
        return jsonify(error="accessible, active, published workflow and serial_number are required"), 400
    product = Product(token=secrets.token_urlsafe(24), serial_number=body["serial_number"], workflow=workflow)
    db.session.add(product); db.session.commit()
    result = product_json(product)
    result.update(qr_url=f"/api/products/{product.token}/qr", traveler_url=f"/api/products/{product.token}/traveler")
    return jsonify(result), 201


def accessible_product(token):
    product = Product.query.filter_by(token=token).first_or_404()
    if not can_access(current_user(), product.workflow.application):
        return None
    return product


@bp.get("/products/<token>")
@login_required
def get_product(token):
    product = accessible_product(token)
    return jsonify(product_json(product)) if product else (jsonify(error="insufficient access"), 403)


@bp.get("/products/<token>/events")
@login_required
def events(token):
    product = accessible_product(token)
    if not product: return jsonify(error="insufficient access"), 403
    return jsonify([{"action": e.action, "step_index": e.step_index, "station_key": e.station_key,
                     "operator": e.user.username, "data": e.data, "sensor_data": e.sensor_data,
                     "created_at": e.created_at.isoformat()} for e in product.events])


@bp.get("/products/<token>/qr")
@login_required
def qr(token):
    product = accessible_product(token)
    if not product: return jsonify(error="insufficient access"), 403
    output = io.BytesIO(); qrcode.make(product.token).save(output, "PNG"); output.seek(0)
    return send_file(output, mimetype="image/png", download_name=f"{product.serial_number}.png")


@bp.get("/products/<token>/traveler")
@login_required
def traveler(token):
    product = accessible_product(token)
    if not product: return jsonify(error="insufficient access"), 403
    output = io.BytesIO(); pdf = canvas.Canvas(output, pagesize=letter)
    pdf.setTitle(f"Traveler {product.serial_number}"); pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(54, 750, f"Traveler: {product.serial_number}")
    y = 710
    for index, step in enumerate(product.workflow.definition["steps"], 1):
        pdf.setFont("Helvetica", 11); pdf.drawString(54, y, f"{index}. {step['name']}  —  station: {step['station_key']}"); y -= 24
    from reportlab.lib.utils import ImageReader
    for x, action, label in ((54, "next", "START / NEXT"), (300, "previous", "PREVIOUS / REWORK")):
        image_buffer = io.BytesIO(); qrcode.make(action_token(product, action)).save(image_buffer, "PNG"); image_buffer.seek(0)
        pdf.drawImage(ImageReader(image_buffer), x, 90, 160, 160)
        pdf.setFont("Helvetica-Bold", 11); pdf.drawCentredString(x + 80, 72, label)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(54, 48, "Action QR codes are signed. Previous/rework requires supervisor or administrator access.")
    pdf.save(); output.seek(0)
    return send_file(output, mimetype="application/pdf", download_name=f"traveler-{product.serial_number}.pdf")


@bp.post("/scans")
@login_required
def scan():
    body = request.get_json() or {}
    command = decode_action_token(body.get("action_token", "")) if body.get("action_token") else None
    if body.get("action_token") and not command:
        return jsonify(error="invalid action token"), 400
    product_token = command["product"] if command else body.get("product_token")
    requested_action = command["action"] if command else body.get("action", "next")
    if requested_action not in ("next", "previous"):
        return jsonify(error="unsupported scan action"), 400
    product = Product.query.filter_by(token=product_token).first()
    operator = User.query.filter_by(badge_hash=badge_digest(str(body.get("badge", ""))), active=True).first()
    if not product or not operator or not can_access(current_user(), product.workflow.application) or not can_access(operator, product.workflow.application):
        return jsonify(error="invalid product, badge, or access"), 403
    key = body.get("idempotency_key")
    if key and ProcessEvent.query.filter_by(idempotency_key=key).first():
        return jsonify(product_json(product), duplicate=True)
    if requested_action == "previous":
        if current_user().role not in ("supervisor", "admin"):
            return jsonify(error="supervisor access required for rework"), 403
        if product.current_step == 0 and product.step_started_at is None:
            return jsonify(error="product is already at the first step"), 409
        previous_index = product.current_step - 1 if product.step_started_at is None else product.current_step
        product.current_step = max(0, previous_index); product.step_started_at = None; product.status = "rework"
        event = ProcessEvent(product=product, user=operator, step_index=product.current_step,
                             action="rework", station_key=body.get("station_key", "SUPERVISOR"),
                             data=body.get("data", {}), sensor_data={}, idempotency_key=body.get("idempotency_key"))
        db.session.add(event)
        try:
            db.session.commit()
        except StaleDataError:
            db.session.rollback()
            return jsonify(error="product changed during scan; rescan current state"), 409
        return jsonify(product_json(product), action="rework", operator=operator.username)
    if product.status == "complete": return jsonify(error="product is already complete"), 409
    step = product.workflow.definition["steps"][product.current_step]
    if body.get("station_key") != step["station_key"]:
        return jsonify(error="wrong station", expected_station=step["station_key"]), 409
    action = "start" if product.step_started_at is None else "complete"
    if action == "complete":
        errors = validate_step_payload(step, body.get("data", {}), body.get("sensor_data", {}))
        if errors:
            return jsonify(error="step data validation failed", fields=errors), 422
    event = ProcessEvent(product=product, user=operator, step_index=product.current_step, action=action,
                         station_key=body["station_key"], data=body.get("data", {}),
                         sensor_data=body.get("sensor_data", {}), idempotency_key=key)
    if action == "start": product.step_started_at = utcnow(); product.status = "in_progress"
    else:
        product.current_step += 1; product.step_started_at = None
        product.status = "complete" if product.current_step == len(product.workflow.definition["steps"]) else "ready"
    db.session.add(event)
    try:
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        return jsonify(error="product changed during scan; rescan current state"), 409
    return jsonify(product_json(product), action=action, operator=operator.username)
