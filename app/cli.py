import click
from flask.cli import with_appcontext
from datetime import datetime
import secrets

from . import db
from .models import Role, User, ProcessTemplate, Product, Device


def do_seed():
    """Create seed data for the demo application. This is idempotent."""
    # Roles
    operator = Role.query.filter_by(name='operator').first()
    if not operator:
        operator = Role(name='operator')
        db.session.add(operator)

    supervisor = Role.query.filter_by(name='supervisor').first()
    if not supervisor:
        supervisor = Role(name='supervisor')
        db.session.add(supervisor)

    db.session.commit()

    # Admin user
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', full_name='Admin User', badge_id='ADMIN123', role_id=operator.id)
        admin.set_password('changeme')
        db.session.add(admin)

    # Sample process template
    template = ProcessTemplate.query.filter_by(name='Sample Process').first()
    if not template:
        steps = [
            {"name": "Receive"},
            {"name": "Assemble"},
            {"name": "Quality Check"},
            {"name": "Packaging"},
            {"name": "Complete"}
        ]
        template = ProcessTemplate(name='Sample Process', steps=steps)
        db.session.add(template)
        db.session.commit()  # commit to have template.id available

    # Sample product
    product = Product.query.filter_by(barcode='PROD0001').first()
    if not product:
        product = Product(sku='SAMPLE-SKU-001', process_template_id=template.id, barcode='PROD0001')
        db.session.add(product)

    db.session.commit()

    # Device token (hashed) creation
    device = Device.query.filter_by(name='Bridge-1').first()
    if not device:
        token = secrets.token_urlsafe(32)
        device = Device(name='Bridge-1')
        device.set_token(token)
        db.session.add(device)
        db.session.commit()
        # Print token to stdout so developer can copy it — it will not be stored in plaintext
        print('\n=== Device token created ===')
        print('Device name: Bridge-1')
        print('Store this token securely. This is the only time it will be shown:')
        print(token)
        print('============================\n')
    else:
        print('Device Bridge-1 already exists. To rotate token, create a new device or use the shell to set a new token.')


def register_cli(app):
    @click.command('seed-data')
    @with_appcontext
    def seed_cmd():
        """Seed the database with sample roles, a user, a process template, and a product."""
        do_seed()
        click.echo('Seed data created.')

    app.cli.add_command(seed_cmd)
