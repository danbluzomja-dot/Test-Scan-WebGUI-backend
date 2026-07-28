from flask import Blueprint, render_template

from .auth import login_required

bp = Blueprint("web", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/station")
@login_required
def station():
    return render_template("station.html")
