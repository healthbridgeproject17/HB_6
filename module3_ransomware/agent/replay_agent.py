"""Replay agent: runs on the SECOND computer of your test network and reports to the HealthBridge monitor.

SAFETY: this program does not read, write, rename or encrypt any file on this computer and does not scan the
network. It only replays SIMULATED telemetry (18 numbers per window, made by the Module 3 simulator) and sends it
to the server with this machine's token. Nothing about this computer is measured.

    # 1. In the website (Security monitor) add a machine of kind "agent" and copy its token (shown once).
    # 2. On this computer, from the module3_ransomware folder:
    $env:HB_AGENT_TOKEN = "paste-the-token-here"
    .\\.venv\\Scripts\\python.exe agent\\replay_agent.py --server http://192.168.1.10:5000 --family fast_encryptor

The token proves which machine is reporting. It travels unencrypted over http, so use this only on your private test network."""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rwdetect.features import FEATURES, WINDOW_SECONDS  # noqa: E402
from rwdetect.monitor import demo_stream  # noqa: E402
from rwdetect.simulate import FAMILIES  # noqa: E402

PATH = "/api/v1/security/telemetry"


def post(url, token, window, timeout=10):
    """Send one window. Returns (status code, message). Never raises for HTTP errors."""
    req = urllib.request.Request(url, data=json.dumps({"window": window}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Agent-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as exc:
        try:
            msg = json.loads(exc.read().decode()).get("error", "")
        except Exception:
            msg = ""
        return exc.code, msg


def main(argv=None):
    ap = argparse.ArgumentParser(description="Replay SIMULATED telemetry to the HealthBridge security monitor.")
    ap.add_argument("--server", required=True, help="backend address, e.g. http://192.168.1.10:5000")
    ap.add_argument("--token", default=None, help="agent token (better: set the HB_AGENT_TOKEN environment variable)")
    ap.add_argument("--family", default="fast_encryptor", choices=["benign", *FAMILIES], help="what the simulated machine does")
    ap.add_argument("--lead-in", type=int, default=8, help="normal windows before the simulated attack starts")
    ap.add_argument("--interval", type=float, default=float(WINDOW_SECONDS), help="seconds between windows (5 = real time, 2 = quicker demo)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--windows", type=int, default=0, help="stop after this many windows (0 = play everything)")
    a = ap.parse_args(argv)

    token = a.token or os.environ.get("HB_AGENT_TOKEN", "")
    if not token:
        sys.exit("No token. Set HB_AGENT_TOKEN (copy it from the Security monitor page when you add the machine).")
    if not a.server.startswith(("http://", "https://")):
        sys.exit("--server must start with http:// or https://")
    if not 1 <= a.interval <= 60:
        sys.exit("--interval must be between 1 and 60 seconds (the server accepts at most 30 windows per minute).")

    seed = a.seed if a.seed is not None else int(time.time()) % 1_000_000
    rows = demo_stream(a.family, seed, lead_in=a.lead_in)
    if a.windows:
        rows = rows[:a.windows]
    url = a.server.rstrip("/") + PATH
    print(f"[agent] replaying {len(rows)} SIMULATED windows ({a.family}) to {a.server} every {a.interval:g}s. Nothing on this computer is touched.")

    failures = 0
    for i, row in enumerate(rows, start=1):
        window = {f: row[f] for f in FEATURES}
        for attempt in range(2):
            try:
                code, msg = post(url, token, window)
            except (urllib.error.URLError, OSError) as exc:
                code, msg = 0, f"cannot reach the server ({exc})"
            if code == 429 and attempt == 0:
                print("[agent] server says slow down; waiting 10 s")
                time.sleep(10)
                continue
            break
        if code == 200:
            failures = 0
            print(f"[agent] window {i:3d}/{len(rows)} sent")
        elif code == 401:
            sys.exit("[agent] the server rejected the token (wrong, replaced, or machine disabled). Stopping.")
        elif code == 503:
            sys.exit(f"[agent] the server's detection engine is not available: {msg}. Stopping.")
        else:
            failures += 1
            print(f"[agent] window {i:3d} failed: {code or 'no connection'} {msg}")
            if failures >= 5:
                sys.exit("[agent] 5 failures in a row. Stopping.")
        time.sleep(a.interval)
    print("[agent] finished.")


if __name__ == "__main__":
    main()
