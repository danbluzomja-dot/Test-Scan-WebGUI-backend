from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from . import db, login_manager


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(200))
    password_hash = db.Column(db.String(255), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'))
    role = db.relationship('Role')
    badge_id = db.Column(db.String(100), unique=True)  # for scanned employee badges
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def get_role(self):
        return self.role.name if self.role else None

    def __repr__(self):
        return f"<User {self.username}>"


class ProcessTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    steps = db.Column(db.JSON, nullable=False)  # list of step definitions

    def __repr__(self):
        return f"<ProcessTemplate {self.name}>"


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(100))
    process_template_id = db.Column(db.Integer, db.ForeignKey('process_template.id'))
    process = db.relationship('ProcessTemplate')
    barcode = db.Column(db.String(255), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    current_step_index = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='in_progress')

    def __repr__(self):
        return f"<Product {self.barcode}>"


class TravelerLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), index=True)
    product = db.relationship('Product')
    step_index = db.Column(db.Integer)
    step_name = db.Column(db.String(200))
    started_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    started_at = db.Column(db.DateTime)
    completed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    def __repr__(self):
        return f"<TravelerLog product={self.product_id} step={self.step_index}>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
