# Run from the backend folder:  .\setup.ps1
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item .env.example .env; Write-Host "Created .env - open it and paste your NeonDB DATABASE_URL" }
.\.venv\Scripts\python.exe -m pytest
Write-Host "Setup finished. Start the API with:  .\.venv\Scripts\python.exe run.py"
