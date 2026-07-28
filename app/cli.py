import click
from flask.cli import with_appcontext
from datetime import datetime

from . import db
from .models import Role, User, ProcessTemplate, Product


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


def register_cli(app):
    @click.command('seed-data')
    @with_appcontext
    def seed_cmd():
        """Seed the database with sample roles, a user, a process template, and a product."""
        do_seed()
        click.echo('Seed data created.')

    app.cli.add_command(seed_cmd)
