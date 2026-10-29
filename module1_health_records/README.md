# Module 1: Digital Health Records

Run order (two PowerShell windows):

1. API:       cd backend ; .\.venv\Scripts\python.exe run.py        -> http://127.0.0.1:5000
2. Website:   cd frontend ; npm install (first time) ; npm run dev   -> http://localhost:5173

The website forwards /api calls to the API (see frontend/vite.config.js).
Roles: patient, doctor, admin. Permissions are enforced by the backend.
