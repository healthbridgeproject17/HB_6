# Module 3 design: ransomware detection (safe, simulated)

## Safety statement
This module contains no malware and nothing that changes files or networks. The "simulator" only draws numbers from statistical descriptions of normal use and of ransomware-like behaviour.
The planned "isolation" response only records a SIMULATED action and recommends what a person should do. It never alters a real machine.

## Idea
An agent on each protected machine reports 18 numbers every 5 seconds (file activity, process and command activity, network behaviour). A model scores each window from 0 to 1. An alert needs 2 high windows out of the last 3, then a cooldown.
Alerts become incidents with a risk level, and a person decides what to do.

| Group | Features |
|---|---|
| Files and processes | files modified / renamed / deleted per second, share of renames that change the extension, write entropy, share of high-entropy writes, folders touched, new processes, backup-tampering commands, CPU, disk writes |
| Network | new connections per second, internal machines contacted on file-sharing ports, failed DNS look-ups, bytes out, out/in ratio, never-seen destinations, beacon regularity |

## Why synthetic data, and what that means
No real dataset was available. The simulator encodes published descriptions of four behaviour families (fast encryptor, slow "low and slow" encryptor that sleeps, network spreader, data thief that also encrypts)
and many kinds of ordinary use, including cases that look like attacks (archiving, photo imports, IT admin work, file-server use).
Models learn the simulator's assumptions, so scores are a demonstration of the method and NOT a claim about real-world detection. The model card states this and shows:
unseen-family results, confidence intervals, a shortcut check, and the false-alarm cost of each sensitivity setting.
(An early version had a shortcut: a constant value in every attack window. It was caught because that feature dominated the importance table and every result was 100%. It is now covered by a regression test.)

## Phases
| Phase | What | Status |
|---|---|---|
| 3.1 | Feature schema, safe simulator, data set, split by whole run | done |
| 3.2 | Model comparison, honest evaluation, model card, shipped model, demo | done |
| 3.3 | Monitor service: receives telemetry, scores, alert rule per machine, risk levels, incidents in the database, simulated response | done (see MODULE3_MONITOR.md) |
| 3.4 | Dark security dashboard (live feed, machines, incidents, metrics, response controls) | done (admin page `/admin/security`) |
| 3.5 | Optional real-metrics agent for your test computers (benign counters only), integration with the website and permissions | next |

## Using a real dataset later
Map its columns to the 18 features in `rwdetect/features.py` (or retrain on whichever subset it provides), load it with `rwdetect.dataset.load_csv`, and run `python -m rwdetect.train`. Split by machine or capture session, never by window.
