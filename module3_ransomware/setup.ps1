# Run from the module3_ransomware folder:  .\setup.ps1
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
Write-Host "Setup finished. Try:  .\.venv\Scripts\python.exe -m rwdetect.demo --family fast_encryptor"
