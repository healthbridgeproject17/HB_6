"""The telemetry a monitoring agent reports for each 5-second window.

Eighteen numbers, in two groups: what the endpoint does to files, and what it
does on the network. Real agents can measure all of these (file-system
filter/audit events, process events, flow logs). Nothing here is a packet
payload or a file's content: only counts, rates and entropy."""
import math

WINDOW_SECONDS = 5

# name: (group, description, lowest, highest)
FEATURE_INFO = {
    "files_modified_per_s": ("files", "files written or changed per second", 0, 5000),
    "files_renamed_per_s": ("files", "files renamed per second", 0, 5000),
    "files_deleted_per_s": ("files", "files deleted per second", 0, 5000),
    "ext_change_ratio": ("files", "share of renamed files whose extension changed (0-1)", 0, 1),
    "write_entropy_mean": ("files", "average randomness of written data, bits per byte (0-8); compressed or encrypted data is near 8", 0, 8),
    "high_entropy_write_ratio": ("files", "share of writes with entropy above 7.5 (0-1)", 0, 1),
    "distinct_dirs_touched": ("files", "different folders written to in the window", 0, 100000),
    "new_process_count": ("files", "processes started in the window", 0, 10000),
    "suspicious_cmd_count": ("files", "runs of commands that tamper with backups or recovery (shadow copies, boot recovery)", 0, 1000),
    "cpu_percent": ("files", "processor use (0-100)", 0, 100),
    "disk_write_mb_per_s": ("files", "megabytes written to disk per second", 0, 100000),
    "new_conn_per_s": ("network", "new outbound connections per second", 0, 100000),
    "smb_distinct_hosts": ("network", "different internal machines contacted on file-sharing ports", 0, 100000),
    "dns_nxdomain_per_s": ("network", "failed name look-ups per second (random-looking domains)", 0, 100000),
    "bytes_out_mb_per_s": ("network", "megabytes sent out per second", 0, 100000),
    "out_in_ratio": ("network", "bytes sent divided by bytes received", 0, 100000),
    "rare_dest_count": ("network", "connections to destinations never seen before on this machine", 0, 100000),
    "beacon_regularity": ("network", "how clock-like the outbound connections are (0 random, 1 perfectly periodic)", 0, 1),
}
FEATURES = list(FEATURE_INFO)
NETWORK_FEATURES = [f for f, v in FEATURE_INFO.items() if v[0] == "network"]
FILE_FEATURES = [f for f, v in FEATURE_INFO.items() if v[0] == "files"]


class BadWindow(ValueError):
    """A telemetry window that cannot be scored (missing or non-numeric fields)."""


def clean_window(window: dict) -> dict:
    """Validate one window from an agent. Missing or non-numeric fields are an error;
    out-of-range numbers are clipped (an agent bug must not crash the monitor)."""
    out = {}
    for name, (_, _, lo, hi) in FEATURE_INFO.items():
        if name not in window:
            raise BadWindow(f"missing field '{name}'")
        try:
            value = float(window[name])
        except (TypeError, ValueError):
            raise BadWindow(f"field '{name}' is not a number")
        if not math.isfinite(value):
            raise BadWindow(f"field '{name}' is not a finite number")
        out[name] = min(max(value, lo), hi)
    return out
