# Module 1: Digital Health Records

Run order (two PowerShell windows):

1. API:       cd backend ; .\.venv\Scripts\python.exe run.py        -> http://127.0.0.1:5000
2. Website:   cd frontend ; npm install (first time) ; npm run dev   -> http://localhost:5173

The website forwards /api calls to the API (see frontend/vite.config.js).
Roles: patient, doctor, admin. Permissions are enforced by the backend.

Demo data:  cd backend ; .\.venv\Scripts\flask.exe --app run seed-demo   (see docs/DEMO_DATA.md)
Security:   see docs/SECURITY.md

Document analysis (Module 2 inside this server): the backend requirements now include Module 2's libraries.
    cd backend ; .\.venv\Scripts\python.exe -m pip install -r requirements.txt     (first time, a few hundred MB)
    .\.venv\Scripts\flask.exe --app run db upgrade
See docs\WORKFLOW.md.
