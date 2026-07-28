from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


user_applications = db.Table(
    "user_applications",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("application_id", db.Integer, db.ForeignKey("applications.id"), primary_key=True),
)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    badge_hash = db.Column(db.String(64), unique=True, nullable=True, index=True)
    role = db.Column(db.String(20), nullable=False, default="operator")
    active = db.Column(db.Boolean, nullable=False, default=True)
    applications = db.relationship("Application", secondary=user_applications, back_populates="users")

    def set_password(self, value):
        self.password_hash = generate_password_hash(value)

    def check_password(self, value):
        return check_password_hash(self.password_hash, value)


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    logo_url = db.Column(db.String(500))
    active = db.Column(db.Boolean, nullable=False, default=True)
    users = db.relationship("User", secondary=user_applications, back_populates="applications")
    workflows = db.relationship("Workflow", back_populates="application")


class Workflow(db.Model):
    __tablename__ = "workflows"
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    active = db.Column(db.Boolean, nullable=False, default=True)
    published = db.Column(db.Boolean, nullable=False, default=False)
    definition = db.Column(db.JSON, nullable=False)
    application = db.relationship("Application", back_populates="workflows")


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    serial_number = db.Column(db.String(120), unique=True, nullable=False)
    workflow_id = db.Column(db.Integer, db.ForeignKey("workflows.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ready")
    current_step = db.Column(db.Integer, nullable=False, default=0)
    step_started_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    revision = db.Column(db.Integer, nullable=False, default=1)
    workflow = db.relationship("Workflow")
    events = db.relationship("ProcessEvent", back_populates="product", order_by="ProcessEvent.id")
    __mapper_args__ = {"version_id_col": revision}


class ProcessEvent(db.Model):
    __tablename__ = "process_events"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    step_index = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)
    station_key = db.Column(db.String(80), nullable=False)
    data = db.Column(db.JSON, nullable=False, default=dict)
    sensor_data = db.Column(db.JSON, nullable=False, default=dict)
    idempotency_key = db.Column(db.String(100), unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    product = db.relationship("Product", back_populates="events")
    user = db.relationship("User")
