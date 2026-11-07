# Module 3: Ransomware detection (Phases 3.1 and 3.2: data and model)

A SAFE project: it simulates telemetry (numbers) and detects patterns in it. There is no malware, no encryption code, and nothing that changes
files or networks. See `docs/MODULE3_DESIGN.md`.

    .\setup.ps1                                        # environment, packages, tests
    .\.venv\Scripts\python.exe -m rwdetect.demo --family fast_encryptor     # watch it detect an attack, window by window
    .\.venv\Scripts\python.exe -m rwdetect.demo --family slow_drip --seed 4 # a slow attacker (harder)
    .\.venv\Scripts\python.exe -m rwdetect.demo --family benign             # a normal machine
    .\.venv\Scripts\python.exe -m rwdetect.train                            # rebuild data, compare models, write models\ (about 3-4 minutes)
    .\.venv\Scripts\python.exe -m rwdetect.train --small                    # quick version

Results and limits: `models\MODEL_CARD.md` (also in docs\). `data\sample_windows.csv` is a small sample of the generated data you can open in Excel.
