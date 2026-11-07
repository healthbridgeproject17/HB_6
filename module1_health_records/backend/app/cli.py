import os

import click

from .extensions import db
from .models import User


def register_cli(app):
    @app.cli.command("seed-admin")
    def seed_admin():
        """Create the one admin account from ADMIN_EMAIL / ADMIN_PASSWORD in .env."""
        email = os.getenv("ADMIN_EMAIL")
        password = os.getenv("ADMIN_PASSWORD")
        if not email or not password:
            raise click.ClickException("Set ADMIN_EMAIL and ADMIN_PASSWORD in .env first.")
        if len(password) < 8:
            raise click.ClickException("ADMIN_PASSWORD must be at least 8 characters.")
        if User.query.filter_by(email=email.lower()).first():
            click.echo("Admin already exists. Nothing to do.")
            return
        admin = User(name="HealthBridge Admin", email=email.lower(), role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin created: {email.lower()}")


    @app.cli.command("reset-admin-password")
    def reset_admin_password():
        """Set the admin password to ADMIN_PASSWORD from .env (for ADMIN_EMAIL)."""
        email = (os.getenv("ADMIN_EMAIL") or "").lower()
        password = os.getenv("ADMIN_PASSWORD")
        if not email or not password:
            raise click.ClickException("Set ADMIN_EMAIL and ADMIN_PASSWORD in .env first.")
        if len(password) < 8:
            raise click.ClickException("ADMIN_PASSWORD must be at least 8 characters.")
        admin = User.query.filter_by(email=email, role="admin").first()
        if admin is None:
            raise click.ClickException("No admin with that email. Run seed-admin instead.")
        admin.set_password(password)
        db.session.commit()
        click.echo("Admin password updated.")


    @app.cli.command("create-admin")
    @click.option("--name", prompt="Admin name")
    @click.option("--email", prompt="Admin email")
    @click.password_option(prompt="Password")
    def create_admin(name, email, password):
        """Create an additional admin account. Admins can only be created here,
        on the server, never through the website."""
        from .utils.validators import clean_email, password_problem

        clean = clean_email(email)
        if not clean:
            raise click.ClickException("Enter a valid email address.")
        problem = password_problem(password)
        if problem:
            raise click.ClickException(problem)
        if len(name.strip()) < 2:
            raise click.ClickException("Name must be at least 2 characters.")
        if User.query.filter_by(email=clean).first():
            raise click.ClickException("An account with this email already exists.")
        admin = User(name=name.strip(), email=clean, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin created: {clean}")


    @app.cli.command("generate-key")
    def generate_key():
        """Print a new random key for DOCUMENT_ENCRYPTION_KEY."""
        from cryptography.fernet import Fernet

        click.echo(Fernet.generate_key().decode())


    @app.cli.command("seed-demo")
    @click.option("--reset", is_flag=True, help="Wipe and recreate the demo patients' clinical data.")
    @click.option("--password", default=None, help="Password for all demo accounts (default: DEMO_PASSWORD or Demo@12345).")
    def seed_demo_command(reset, password):
        """Load FICTIONAL demo doctors, patients, records, prescriptions and documents."""
        from .demo import DOMAIN, seed_demo
        from .utils.validators import password_problem

        password = password or os.getenv("DEMO_PASSWORD") or "Demo@12345"
        problem = password_problem(password)
        if problem:
            raise click.ClickException(problem)
        demo_dir = os.getenv("DEMO_DOCUMENTS_DIR") or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "demo_documents"))
        if not os.path.isfile(os.path.join(demo_dir, "manifest.json")):
            raise click.ClickException(f"Demo documents not found in {demo_dir}")
        try:
            result = seed_demo(password, demo_dir, reset=reset)
        except RuntimeError as exc:
            raise click.ClickException(str(exc))
        if result["skipped"]:
            click.echo("Demo data already exists. Use --reset to recreate it.")
            return
        click.echo("Demo data loaded: " + ", ".join(f"{k}={v}" for k, v in result.items() if k != "skipped"))
        click.echo(f"Log in with any @{DOMAIN} account and password: {password}")


    @app.cli.command("seed-security")
    def seed_security_command():
        """Add three FICTIONAL simulated machines to the security monitor. Safe to run again."""
        from .models import MonitoredMachine
        from .utils.audit import log_action

        added = 0
        for name in ("Reception-PC", "Pharmacy-PC", "Records-Server"):
            if MonitoredMachine.query.filter(db.func.lower(MonitoredMachine.name) == name.lower()).first():
                continue
            db.session.add(MonitoredMachine(name=name, kind="simulated"))
            added += 1
        db.session.commit()
        if added:
            log_action(None, "security_machines_seeded", "machine", None, detail=f"{added} simulated machine(s) added")
        click.echo(f"Security demo ready: {added} simulated machine(s) added.")
