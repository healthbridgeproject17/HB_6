# Model card: HealthBridge ransomware detector (v0.1)

**What it is.** A classifier that scores each 5-second window of endpoint and network telemetry from 0 (normal) to 1 (looks like ransomware),
plus an alert rule: **2 high windows out of the last 3**, then a 12-window quiet period.
Chosen model: **Gradient boosting**. The alert threshold is the one with the fewest false alarms that still catches at least 90% of attacks on validation data.

**What it is NOT.** It is not trained or tested on real ransomware or real company traffic. It is a method demonstration on synthetic data. Do not rely on it to protect real systems.

## Data (synthetic)
106,781 windows (11% attack) from 500 normal virtual machines and 50 attack runs for each of
4 behaviour families (fast_encryptor, slow_drip, network_spreader, double_extortion). Every distribution is an assumption written from published descriptions of ransomware behaviour.
Normal activity includes deliberately confusing cases: archiving (random-looking writes), photo imports (many renames), IT admin work (backup commands), file-server use (many machines contacted).
Each run is an independent virtual machine, and train / validation / test are split by whole run, so no machine is in two sets.

## Models compared (test set, never used for choosing anything)
| Model | PR-AUC | Window recall | Window false-positive rate | Attacks caught (with alert rule) | False alarms per machine-hour |
|---|---|---|---|---|---|
| Logistic regression | 0.939 | 73% | 0.08% | 92% | 0.00 |
| Random forest | 0.979 | 87% | 0.05% | 100% | 0.04 |
| Gradient boosting | 0.988 | 94% | 0.11% | 100% | 0.08 |
| Isolation forest (no attack examples) | 0.776 | 51% | 0.83% | 75% | 0.68 |
| Simple hand-written rule | 0.804 | 62% | 0.41% | 85% | 0.04 |

## Choosing how sensitive to be (chosen model, test data)
A stricter threshold means fewer false alarms but more missed or slower detections. Pick the row that fits how many false alarms people will tolerate.

| Normal windows allowed above threshold | Attacks caught | Median delay (windows) | False alarms per machine-hour | Window recall |
|---|---|---|---|---|
| 0.50% | 100% | 1.0 | 0.239 | 96% |
| 0.20% | 100% | 1.0 | 0.159 | 95% |
| 0.10% (chosen) | 100% | 1.0 | 0.080 | 94% |
| 0.05% | 100% | 2.0 | 0.000 | 93% |
| 0.02% | 100% | 2.0 | 0.000 | 92% |
| 0.01% | 100% | 2.0 | 0.000 | 91% |

## Result for the chosen model with the alert rule
- Attacks caught: **100%** of 40 test attack runs (95% confidence interval 91% to 100%); median delay **1.0 windows (5 s)** after the first malicious activity.
- False alarms: **0.080 per machine-hour** on normal activity, measured over only **25 hours** of test data. The 95% upper bound is **0.29 per machine-hour**: a few dozen hours cannot show a rate this small, so real tuning needs weeks of real normal traffic.
- Window-level false-positive rate and the false alarm rate above are different things: one false alarm needs several high windows in a row.

| Attack family | Caught | Median delay (windows) |
|---|---|---|
| fast_encryptor | 100% | 2.0 |
| slow_drip | 100% | 2.5 |
| network_spreader | 100% | 1.0 |
| double_extortion | 100% | 1.0 |

## Unseen attack types (leave one family out)
Trained without the family in the row, then asked to find it. This is closer to real life than the table above, because real attackers are not in your training data.

| Held-out family | Logistic regression | Random forest | Gradient boosting |
|---|---|---|---|
| fast_encryptor | 92% | 88% | 90% |
| slow_drip | 54% | 70% | 78% |
| network_spreader | 98% | 100% | 100% |
| double_extortion | 100% | 100% | 100% |

## What drives the score (permutation importance on validation data)
| Feature | Meaning | Importance |
|---|---|---|
| files_renamed_per_s | files renamed per second | 0.236 |
| ext_change_ratio | share of renamed files whose extension changed (0-1) | 0.087 |
| rare_dest_count | connections to destinations never seen before on this machine | 0.042 |
| high_entropy_write_ratio | share of writes with entropy above 7.5 (0-1) | 0.039 |
| new_process_count | processes started in the window | 0.036 |
| distinct_dirs_touched | different folders written to in the window | 0.014 |
| smb_distinct_hosts | different internal machines contacted on file-sharing ports | 0.014 |
| suspicious_cmd_count | runs of commands that tamper with backups or recovery (shadow copies, boot recovery) | 0.008 |


## Shortcut check (retrain without one feature at a time)
Baseline PR-AUC 0.988. The five features whose removal hurts most:

| Feature removed | PR-AUC without it |
|---|---|
| new_process_count | 0.966 |
| ext_change_ratio | 0.979 |
| files_renamed_per_s | 0.983 |
| rare_dest_count | 0.983 |
| high_entropy_write_ratio | 0.984 |

If one row collapses, the data has a shortcut or the detector leans on one sensor.

## Limits you should state out loud
1. **Synthetic data.** Scores here show the model learns the assumptions in the simulator (an earlier version of the simulator had a shortcut, found by checking feature importance, which made every result 100%). Real telemetry will be messier and results will be worse.
2. **Base rates.** Real attacks are extremely rare. Even a rate of 0.080 false alarms per machine-hour is about 698 per machine per year, and attacks are rare, so on a real network almost every alert would be a false alarm unless the threshold is tuned on real normal traffic. A real deployment must be tuned on real normal traffic.
3. **Adaptive attackers.** An attacker who knows the thresholds can slow down (see slow_drip) or imitate normal activity.
4. **Telemetry gaps.** The model assumes an agent reports all 18 numbers every 5 seconds. Missing or tampered telemetry is a blind spot.
5. **Model file safety.** The model is a Python pickle (SHA-256 `72332d814f46639b...`). Only load files you created.
6. **Response.** The system recommends and records a SIMULATED isolation. It never changes a real machine or network.
