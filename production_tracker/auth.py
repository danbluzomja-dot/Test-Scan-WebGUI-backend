from functools import wraps

from flask import Blueprint, jsonify, request, session

from .models import User

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def current_user():
    return User.query.get(session.get("user_id")) if session.get("user_id") else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user.active:
            return jsonify(error="authentication required"), 401
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user().role not in roles:
                return jsonify(error="insufficient access"), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


@bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    user = User.query.filter_by(username=body.get("username", "")).first()
    if not user or not user.active or not user.check_password(body.get("password", "")):
        return jsonify(error="invalid credentials"), 401
    session.clear()
    session["user_id"] = user.id
    return jsonify(user={"id": user.id, "username": user.username, "role": user.role})


@bp.post("/logout")
def logout():
    session.clear()
    return "", 204


@bp.get("/me")
@login_required
def me():
    user = current_user()
    return jsonify(id=user.id, username=user.username, role=user.role,
                   applications=[a.key for a in user.applications])
