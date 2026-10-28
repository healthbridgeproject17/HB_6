# HealthBridge project rules
- Root is D:\HB_6. Do not change the folder structure.
- Backend: Flask, API under /api/v1, NeonDB PostgreSQL, Flask-Migrate. Frontend: React + Vite + Tailwind.
- Fictional data only. No real patient data. No real ransomware, only the safe simulator.
- Roles (patient, doctor, admin) are enforced on the backend, never only in the UI.
- Never put secrets in code. Use .env. Never open, print or edit .env.
- Uncertain OCR values must be flagged, never guessed. Advice must never change medicines or doses.
- Run pytest before finishing. Do not edit more files than the task needs.
