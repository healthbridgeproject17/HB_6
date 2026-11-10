"""Sending email. Backends: 'smtp' (real), 'console' (development: written to the server log),
'memory' (tests). Nothing here ever raises into a request: a mail problem is logged, not shown."""
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def send_email(to, subject, body):
    cfg = current_app.config
    backend = cfg["MAIL_BACKEND"]
    try:
        if backend == "memory":
            current_app.extensions.setdefault("outbox", []).append({"to": to, "subject": subject, "body": body})
        elif backend == "smtp":
            if not cfg["SMTP_HOST"]:
                raise RuntimeError("SMTP_HOST is not set")
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = cfg["MAIL_FROM"], to, subject
            msg.set_content(body)
            with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15) as server:
                server.starttls(context=ssl.create_default_context())
                if cfg["SMTP_USER"]:
                    server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
                server.send_message(msg)
        elif cfg["ENV_NAME"] == "production":
            # a link in a log file would be a leaked login: never print it on a live site
            current_app.logger.warning("Email not sent: MAIL_BACKEND is 'console' in production. Set MAIL_BACKEND=smtp.")
            return False
        else:
            current_app.logger.warning("DEV EMAIL to %s | %s\n%s", to, subject, body)
        return True
    except Exception as exc:
        current_app.logger.error("Sending email failed: %s", exc.__class__.__name__)
        return False
