# Module 1 security summary

## Enforced by the backend (not just hidden buttons)
- Roles patient / doctor / admin checked on every request; the role is read from the database, not trusted from the token.
- Patients see only their own data (other patients' ids return 403); doctors read all patients, every access is audited; admins manage accounts but cannot write clinical entries.
- Clinical corrections are new, linked versions with a required reason; originals are never overwritten.
- Prescriptions: only doctors create/confirm; unverified (draft) ones never count as confirmed.

## Accounts and sessions
- Passwords hashed with bcrypt (limit 72 bytes, enforced). Sign-up always creates a patient.
- Admin accounts only via the server command; doctors only via an admin, with a temporary password that must be changed at first login.
- Login tokens last 2 hours; logout, password change and disabling an account end all sessions immediately.
- 5 wrong passwords lock that email for 15 minutes; sign-ups are limited per network.

## Data protection
- Uploaded documents and profile photos are encrypted on disk (Fernet/AES) and only served through permission-checked routes.
- Uploads are verified by real content (not file name), size-limited, renamed randomly; photos are re-encoded (metadata stripped).
- Audit log is append-only: on PostgreSQL a trigger blocks any UPDATE or DELETE.
- API responses are never cached; security headers set; errors never reveal internals; debugger is off by default.
- Production mode refuses to start with weak/default secrets, SQLite, or open CORS.

## Remaining limits (be honest in the viva)
- Doctors can open any patient (as specified); a "care team / break-glass" model would be stricter.
- No email verification, password reset by email, or two-factor login yet.
- Tokens live in sessionStorage (cleared when the tab closes); a cookie-based session would resist XSS better.
- Encryption key and database credentials must be protected and backed up; lose the key and files cannot be opened.
- Deployment must use HTTPS, private file storage and database backups.
