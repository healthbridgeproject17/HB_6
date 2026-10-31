# Run from the module2_medical_ai folder:  .\setup.ps1
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
Write-Host "Setup finished. Try:  .\.venv\Scripts\python.exe -m medai ..\demo_documents\ananya_cbc_iron_report_scan.jpg"
