from datetime import datetime, timezone

import bcrypt

from ..extensions import db

ROLES = ("patient", "doctor", "admin")


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # bumping token_version invalidates every login token of this user (logout,
    # password change, disable); must_change_password forces a new password at
    # first login for accounts created with a temporary password
    token_version = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    must_change_password = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        db.CheckConstraint("role IN ('patient','doctor','admin')", name="ck_users_role"),
    )

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    health_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    dob = db.Column(db.Date)
    sex = db.Column(db.String(10))
    phone = db.Column(db.String(30))
    emergency_contact = db.Column(db.String(120))
    allergies = db.Column(db.Text)
    photo_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("patient", uselist=False))


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    specialty = db.Column(db.String(120))
    license_no = db.Column(db.String(60))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("doctor", uselist=False))
