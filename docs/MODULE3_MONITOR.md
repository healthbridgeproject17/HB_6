# Module 3: security monitor (Phases 3.3 and 3.4)

**Safety:** nothing here changes a real machine, file or network. "Isolate" and "Release" only write a record and an audit entry. The simulator only produces numbers.

## What it does
```
agent or simulator -> 18 numbers per 5 s window -> model score (0-1) -> alert rule (2 of last 3 high windows, then 12-window cooldown)
  -> incident per machine with a risk level -> an admin acknowledges, "isolates" (simulated) and closes it -> every step in the audit log
```
Decisions live in `module3_ransomware/rwdetect/monitor.py` (no web framework, tested on its own). The website backend (`backend/app/monitor_service.py`, `routes/security.py`) only stores them.

## Risk level (easy to check by hand)
Three things add up: model confidence (>= 0.97 gives 2, >= 0.90 gives 1), how many different kinds of suspicious behaviour are visible (encryption, backup tampering, spreading, outside contact; up to 3), and how long it has lasted (30 s gives 1, 2 min gives 2).
Total 0-2 Low, 3 Medium, 4-5 High, 6+ Critical. Within one incident the level only goes up. The incident screen shows the three parts.

## Who can do what
| | Admin | Doctor / patient | Agent (token) |
|---|---|---|---|
| See machines, feed, incidents, model | yes | no | no |
| Add machine, start/stop simulation, respond, close, clear demo data | yes | no | no |
| Send telemetry | no | no | yes, own machine only |

Agent tokens are random, shown once, stored only as a SHA-256 hash, and can be replaced (the old one stops working). Admin actions are audited (`security_*` actions).
Telemetry is limited to 30 windows per minute per machine; only the newest 400 windows per machine are kept.

## Run it
1. `cd module1_health_records\backend`, then `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` (now includes the Module 3 libraries).
2. `.\.venv\Scripts\flask.exe --app run db upgrade` (creates 4 tables; migration `b3d9a4c61e07`).
3. Start the backend and the website as before, log in as admin, open **Admin dashboard, Security monitor**.

## Demo script (about 5 minutes)
0. Open the page and read the short "How to read this page" box; the coloured banner at the top always says in one sentence what is happening.
1. Select Demo-PC-2 (or **Add two demo machines** if the list is empty) and press **Show normal activity**: it stays Normal.
2. Select Demo-PC-1 and press **Show a ransomware attack**. After about 8 normal checks the attack starts; the danger score jumps and an incident opens (usually Critical within a few seconds). Other attack types are under "Other kinds of simulated attack".
3. Read "What stood out" and "How the risk level was reached". Explain that the reasons come from simple rules on the numbers, not from the model's inner workings.
4. **Acknowledge**, then **Isolate machine (simulated)**: point at the "SIMULATION" note. Then **Close incident** as resolved with a note.
5. Admin dashboard, Audit log: show `security_incident_opened`, `security_isolation_simulated`, `security_incident_resolved`.
6. Scroll to "How well does the detector work?": read the "In plain words" box and the caveats aloud (synthetic data, small false-alarm sample, slow family caught less often and later).
7. Optional, two real computers: see "Two-computer demo" below.

## Two-computer demo (private test network only)
The agent on computer 2 replays SIMULATED windows. It measures nothing about that computer and touches none of its files, so the demo shows the network path and the token check, not real ransomware detection.

**Computer 1 (server, runs the website and backend)**
1. Find its address: `ipconfig` (the IPv4 address, e.g. 192.168.1.10).
2. Allow the backend port for the private network only (PowerShell as administrator):
   `New-NetFirewallRule -DisplayName "HealthBridge lab API" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private`
3. Start the backend so other computers can reach it: `cd module1_health_records\backend` then `.\.venv\Scripts\flask.exe --app run run --host 0.0.0.0 --port 5000`.
4. Website, Security monitor: add a machine of kind **Real computer with an agent** (e.g. `Lab-PC-2`). Copy the token now; it is shown only once.

**Computer 2 (monitored machine)**
1. Copy the whole `module3_ransomware` folder and run `.\setup.ps1` in it once (creates its environment, about 5 minutes).
2. `$env:HB_AGENT_TOKEN = "paste-the-token-here"`
3. `.\.venv\Scripts\python.exe agent\replay_agent.py --server http://192.168.1.10:5000 --family fast_encryptor --interval 2`
4. Watch computer 1: Lab-PC-2 turns Normal, then an incident opens a few windows after the simulated attack starts.

**Afterwards:** stop the backend, then remove the firewall rule: `Remove-NetFirewallRule -DisplayName "HealthBridge lab API"`. On the website, use "New token" or Disable on the machine so the old token stops working.
The token travels unencrypted over http, which is acceptable only on your own private network. Never type a token into a chat or save it in a file in the project.
Try the failure cases in the viva too: a wrong token is refused (401) and the agent stops; Disable the machine and the agent is refused as well.

## Likely viva questions
- **Is this real ransomware detection?** It demonstrates the method on synthetic data. The numbers show the pipeline works, not real-world accuracy.
- **What was the shortcut?** Early simulated attacks had a constant value, so every result was 100%. Feature importance exposed it; it is fixed and covered by a regression test.
- **Why 2 of 3 windows?** One noisy window should not raise an alarm; the cost is a few seconds of delay.
- **Why is isolation simulated?** A wrong automatic isolation of a hospital machine is itself harmful; a person decides, and the system records and recommends.
- **Why do slow attacks do worse?** A family the model never saw, that sleeps between bursts, is caught less often and later (see the model card).
- **How are agents authenticated?** Per-machine random token, hashed in the database, rotatable, rate limited.
