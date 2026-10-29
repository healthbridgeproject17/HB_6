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
