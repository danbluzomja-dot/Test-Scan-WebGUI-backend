import io
from flask import Blueprint, jsonify, request, send_file, current_app, abort
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from . import db, socketio
from .models import User, Product, TravelerLog, ProcessTemplate
from .qrcode_utils import generate_qr_bytes

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/auth/login', methods=['POST'])
def login():
    """Simple badge-based login: POST {"badge_id": "..."}
    For development this logs the user in via Flask-Login and returns user info.
    """
    data = request.get_json() or {}
    badge_id = data.get('badge_id')
    if not badge_id:
        return jsonify({'error': 'badge_id required'}), 400
    user = User.query.filter_by(badge_id=badge_id, is_active=True).first()
    if not user:
        return jsonify({'error': 'user not found for badge'}), 404
    login_user(user)
    return jsonify({'id': user.id, 'username': user.username, 'full_name': user.full_name})


@api_bp.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'ok': True})


@api_bp.route('/product/<string:barcode>', methods=['GET'])
def get_product(barcode):
    product = Product.query.filter_by(barcode=barcode).first()
    if not product:
        return jsonify({'error': 'product not found'}), 404
    template = None
    if product.process:
        template = product.process.steps
    return jsonify({
        'id': product.id,
        'barcode': product.barcode,
        'sku': product.sku,
        'current_step_index': product.current_step_index,
        'status': product.status,
        'process_steps': template,
    })


@api_bp.route('/product/<string:barcode>/qr', methods=['GET'])
def product_qr(barcode):
    """Return a PNG QR code for the product as image/png"""
    product = Product.query.filter_by(barcode=barcode).first()
    if not product:
        abort(404)
    # Payload can be a short URL or token; for now, encode the barcode
    img_bytes = generate_qr_bytes(product.barcode)
    return send_file(io.BytesIO(img_bytes), mimetype='image/png', as_attachment=False, download_name=f'{barcode}.png')


@api_bp.route('/product/<string:barcode>/start', methods=['POST'])
@login_required
def start_step(barcode):
    """Start the current step for the product. Requires an authenticated user (badge scan login)."""
    product = Product.query.filter_by(barcode=barcode).first()
    if not product:
        return jsonify({'error': 'product not found'}), 404
    # Create a TravelerLog if not exists for this step
    existing = TravelerLog.query.filter_by(product_id=product.id, step_index=product.current_step_index).first()
    if existing and existing.started_at:
        return jsonify({'ok': True, 'message': 'step already started'})

    log = existing or TravelerLog(product_id=product.id, step_index=product.current_step_index,
                                  step_name=(product.process.steps[product.current_step_index]['name'] if product.process else None))
    log.started_by = current_user.id
    log.started_at = datetime.utcnow()
    try:
        db.session.add(log)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'could not start step'}), 500

    # emit socket update
    socketio.emit('product.update', {'product_id': product.id, 'barcode': product.barcode, 'current_step_index': product.current_step_index})
    return jsonify({'ok': True})


@api_bp.route('/product/<string:barcode>/complete', methods=['POST'])
@login_required
def complete_step(barcode):
    """Complete the current step and advance the product to next step."""
    product = Product.query.filter_by(barcode=barcode).first()
    if not product:
        return jsonify({'error': 'product not found'}), 404

    log = TravelerLog.query.filter_by(product_id=product.id, step_index=product.current_step_index).first()
    if not log or not log.started_at:
        # no started log; optionally create one
        log = TravelerLog(product_id=product.id, step_index=product.current_step_index,
                          step_name=(product.process.steps[product.current_step_index]['name'] if product.process else None))
        log.started_by = current_user.id
        log.started_at = datetime.utcnow()

    if log.completed_at:
        return jsonify({'ok': True, 'message': 'step already completed'})

    log.completed_by = current_user.id
    log.completed_at = datetime.utcnow()
    # advance product
    product.current_step_index = product.current_step_index + 1
    # if beyond steps, mark finished
    if product.process and product.current_step_index >= len(product.process.steps):
        product.status = 'complete'

    try:
        db.session.add(log)
        db.session.add(product)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error': 'could not complete step', 'details': str(exc)}), 500

    socketio.emit('product.update', {'product_id': product.id, 'barcode': product.barcode, 'current_step_index': product.current_step_index})
    return jsonify({'ok': True, 'new_step_index': product.current_step_index, 'status': product.status})


@api_bp.route('/product/<string:barcode>/traveler.pdf', methods=['GET'])
def traveler_pdf(barcode):
    product = Product.query.filter_by(barcode=barcode).first()
    if not product:
        return jsonify({'error': 'product not found'}), 404

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    p.setFont("Helvetica", 12)
    p.drawString(40, height - 40, f"Traveler for product: {product.barcode}")
    p.drawString(40, height - 60, f"SKU: {product.sku}")
    p.drawString(40, height - 80, f"Status: {product.status}")

    # Draw steps
    y = height - 120
    steps = product.process.steps if product.process else []
    for idx, s in enumerate(steps):
        marker = '->' if idx == product.current_step_index else '  '
        p.drawString(40, y, f"{marker} Step {idx}: {s.get('name')}")
        y -= 18
        if y < 80:
            p.showPage()
            y = height - 40

    # Add QR for product at the bottom-left
    qr_bytes = generate_qr_bytes(product.barcode)
    qr_io = io.BytesIO(qr_bytes)
    # save image temporarily using reportlab's drawImage requires a filename or a PIL Image; use drawInlineImage
    try:
        from PIL import Image
        qr_io.seek(0)
        pil = Image.open(qr_io)
        p.drawInlineImage(pil, width - 150, 40, 100, 100)
    except Exception:
        # ignore image if PIL not available
        pass

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=False, download_name=f'{barcode}_traveler.pdf')

