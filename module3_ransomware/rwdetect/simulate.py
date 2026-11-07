"""A SAFE telemetry simulator. It never touches files or the network: it only
draws numbers, window by window, from statistical descriptions of (a) ordinary
computer use and (b) four ransomware behaviour families. There is no encryption
code and nothing here can harm a machine.

IMPORTANT: every distribution below is an ASSUMPTION written from published
descriptions of ransomware behaviour. A model trained on this data learns these
assumptions. Treat results as a demonstration of the method, not as a measure of
real-world detection. Hard cases are included on purpose (archiving writes
random-looking data, photo imports rename thousands of files, IT staff run backup
commands, file-server users contact many machines) so no single number gives
the answer away."""
import numpy as np
import pandas as pd

from .features import FEATURES, WINDOW_SECONDS  # noqa: F401

FAMILIES = ["fast_encryptor", "slow_drip", "network_spreader", "double_extortion"]


def _ln(rng, median, sigma=0.45):
    return median * rng.lognormal(0.0, sigma)


def _bounded(rng, mean, sd, lo=0.0, hi=1.0):
    return float(np.clip(rng.normal(mean, sd), lo, hi))


# profile: (weight, dict of feature -> median / (mean, sd) / ('poisson', lam))
P = {
    "idle": (0.10, dict(fm=0.15, fr=0.01, fd=0.01, ext=(0.0, 0.02), ent=(4.0, 1.2), her=(0.05, 0.05), dirs=1.5, np=0.05, sc=0.0, cpu=3, dw=0.03, nc=0.3, smb=0.03, dns=0.02, bo=0.02, oi=0.5, rare=0.05, beacon=(0.15, 0.1))),
    "office": (0.22, dict(fm=1.5, fr=0.15, fd=0.08, ext=(0.30, 0.25), ent=(6.3, 0.6), her=(0.35, 0.15), dirs=4, np=0.3, sc=0.0, cpu=12, dw=0.4, nc=1.2, smb=0.2, dns=0.15, bo=0.06, oi=0.4, rare=0.2, beacon=(0.25, 0.1))),
    "browsing": (0.18, dict(fm=0.9, fr=0.05, fd=0.3, ext=(0.55, 0.30), ent=(7.0, 0.4), her=(0.5, 0.2), dirs=3, np=0.2, sc=0.0, cpu=15, dw=0.3, nc=4, smb=0.0, dns=0.6, bo=0.1, oi=0.12, rare=1.2, beacon=(0.3, 0.12))),
    "cloud_backup": (0.05, dict(fm=0.2, fr=0.02, fd=0.01, ext=(0.0, 0.02), ent=(4.5, 0.8), her=(0.1, 0.08), dirs=3, np=0.1, sc=0.0, cpu=20, dw=0.1, nc=1.5, smb=0.0, dns=0.05, bo=3.5, oi=25, rare=0.1, beacon=(0.65, 0.12))),
    "software_update": (0.04, dict(fm=8, fr=2, fd=1.5, ext=(0.35, 0.2), ent=(6.8, 0.4), her=(0.45, 0.15), dirs=15, np=4, sc=0.05, cpu=40, dw=6, nc=3, smb=0.0, dns=0.4, bo=0.1, oi=0.05, rare=1.0, beacon=(0.2, 0.1))),
    "bulk_copy": (0.04, dict(fm=15, fr=0.3, fd=0.05, ext=(0.15, 0.15), ent=(7.2, 0.3), her=(0.65, 0.15), dirs=8, np=0.3, sc=0.0, cpu=25, dw=25, nc=1, smb=0.6, dns=0.05, bo=0.2, oi=0.1, rare=0.05, beacon=(0.2, 0.1))),
    "dev_build": (0.05, dict(fm=40, fr=3, fd=6, ext=(0.5, 0.3), ent=(5.0, 0.5), her=(0.12, 0.08), dirs=20, np=25, sc=0.0, cpu=80, dw=8, nc=2, smb=0.0, dns=0.1, bo=0.05, oi=0.1, rare=0.2, beacon=(0.15, 0.1))),
    "video_call": (0.06, dict(fm=0.2, fr=0.02, fd=0.02, ext=(0.0, 0.02), ent=(4.5, 0.8), her=(0.1, 0.08), dirs=2, np=0.1, sc=0.0, cpu=35, dw=0.1, nc=2, smb=0.0, dns=0.1, bo=1.0, oi=1.2, rare=1.5, beacon=(0.9, 0.05))),
    "antivirus_scan": (0.04, dict(fm=0.3, fr=0.02, fd=0.02, ext=(0.0, 0.02), ent=(5.0, 0.6), her=(0.15, 0.08), dirs=30, np=1, sc=0.0, cpu=60, dw=0.3, nc=0.5, smb=0.0, dns=0.05, bo=0.03, oi=0.2, rare=0.1, beacon=(0.2, 0.1))),
    "archive_compress": (0.05, dict(fm=1, fr=0.05, fd=0.02, ext=(0.0, 0.02), ent=(7.9, 0.05), her=(0.95, 0.03), dirs=4, np=0.3, sc=0.0, cpu=55, dw=18, nc=0.5, smb=0.0, dns=0.02, bo=0.03, oi=0.2, rare=0.0, beacon=(0.15, 0.1))),
    "photo_import": (0.04, dict(fm=6, fr=8, fd=0.1, ext=(0.08, 0.1), ent=(7.4, 0.3), her=(0.75, 0.1), dirs=3, np=0.4, sc=0.0, cpu=20, dw=15, nc=1, smb=0.0, dns=0.1, bo=0.1, oi=0.1, rare=0.1, beacon=(0.2, 0.1))),
    "git_operations": (0.03, dict(fm=30, fr=20, fd=15, ext=(0.12, 0.1), ent=(5.2, 0.5), her=(0.15, 0.08), dirs=12, np=8, sc=0.0, cpu=30, dw=3, nc=1.5, smb=0.0, dns=0.1, bo=0.2, oi=0.3, rare=0.3, beacon=(0.2, 0.1))),
    "it_admin_work": (0.05, dict(fm=2, fr=0.3, fd=0.2, ext=(0.2, 0.2), ent=(5.5, 0.6), her=(0.2, 0.1), dirs=6, np=5, sc=1.0, cpu=20, dw=0.5, nc=3, smb=1.5, dns=0.3, bo=0.1, oi=0.3, rare=0.5, beacon=(0.3, 0.12))),
    "file_server_user": (0.05, dict(fm=3, fr=0.3, fd=0.2, ext=(0.15, 0.15), ent=(6.5, 0.5), her=(0.4, 0.15), dirs=6, np=0.3, sc=0.0, cpu=15, dw=1.5, nc=3, smb=3.5, dns=0.2, bo=0.1, oi=0.3, rare=0.3, beacon=(0.25, 0.1))),
}
PROFILES = list(P)
_W = np.array([P[k][0] for k in PROFILES])
_W = _W / _W.sum()


def _host(rng):
    """Each virtual machine is a bit busier or quieter than the average one."""
    return {"act": rng.lognormal(0, 0.35), "net": rng.lognormal(0, 0.35)}


def benign_window(rng, profile, host):
    p = P[profile][1]
    a, n = host["act"], host["net"]
    burst = 1.0
    if rng.random() < 0.03:                   # now and then, ordinary work spikes
        burst = rng.uniform(3, 10)
    w = {}
    w["fm"] = _ln(rng, p["fm"] * a * burst, 0.5)
    w["fr"] = _ln(rng, p["fr"] * a * burst, 0.6)
    w["fd"] = _ln(rng, p["fd"] * a * burst, 0.6)
    w["ext"] = _bounded(rng, *p["ext"])
    w["ent"] = _bounded(rng, *p["ent"], lo=0, hi=8)
    w["her"] = _bounded(rng, *p["her"])
    w["dirs"] = max(0.0, float(rng.poisson(max(p["dirs"] * a, 0.01))))
    w["np"] = float(rng.poisson(p["np"] * a * burst))
    w["sc"] = float(rng.poisson(p["sc"]))
    w["cpu"] = float(np.clip(_ln(rng, p["cpu"], 0.35) * (0.7 + 0.3 * a), 0, 100))
    w["dw"] = _ln(rng, p["dw"] * a * burst, 0.5)
    w["nc"] = _ln(rng, p["nc"] * n, 0.5)
    w["smb"] = float(rng.poisson(p["smb"]))
    w["dns"] = _ln(rng, p["dns"] * n, 0.6)
    w["bo"] = _ln(rng, p["bo"] * n, 0.5)
    w["oi"] = _ln(rng, p["oi"], 0.5)
    w["rare"] = float(rng.poisson(p["rare"] * n))
    w["beacon"] = _bounded(rng, *p["beacon"])
    if w["fr"] < 0.02:
        w["ext"] = 0.0                         # almost no renames: the ratio means nothing
    return w


def _blend(base, att):
    """Ransomware activity happens ON TOP of whatever the user is already doing."""
    w = {}
    for k in ("fm", "fr", "fd", "dirs", "np", "sc", "dw", "nc", "smb", "dns", "bo", "rare"):
        w[k] = base[k] + att.get(k, 0.0)
    w["cpu"] = min(100.0, base["cpu"] + att.get("cpu", 0.0))
    fm_total = base["fm"] + att.get("fm", 0.0) + 1e-9
    w["ent"] = (base["ent"] * base["fm"] + att.get("ent", base["ent"]) * att.get("fm", 0.0)) / fm_total if att.get("fm", 0) else base["ent"]
    w["her"] = (base["her"] * base["fm"] + att.get("her", base["her"]) * att.get("fm", 0.0)) / fm_total if att.get("fm", 0) else base["her"]
    fr_total = base["fr"] + att.get("fr", 0.0)
    w["ext"] = (base["ext"] * base["fr"] + att.get("ext", 0.0) * att.get("fr", 0.0)) / fr_total if fr_total > 0.02 else 0.0
    bytes_in = base["bo"] / max(base["oi"], 1e-3) + att.get("bi", 0.0)
    w["oi"] = w["bo"] / max(bytes_in, 0.01)
    w["beacon"] = max(base["beacon"], att.get("beacon", 0.0))
    return w


def _attack_windows(rng, family):
    """Yields (phase, contribution) for every window of an attack, in order."""
    out = []

    def encrypt(n, rate_median, rename_share=(0.7, 1.0), ext=(0.9, 1.0), ent=(7.85, 7.99), her=(0.93, 1.0), cpu=(30, 60), net=0.0, sigma=0.5, duty=1.0):
        share, e = rng.uniform(*rename_share), rng.uniform(*ext)
        rate = _ln(rng, rate_median, 0.6)
        for _ in range(n):
            if rng.random() > duty:                 # the malware sleeps to avoid attention: nothing to see in this window
                out.append(("sleep", {}))
                continue
            r = _ln(rng, rate, sigma)
            out.append(("encrypt", dict(fm=r, fr=r * share * rng.uniform(0.8, 1.1), fd=r * rng.uniform(0, 0.1), ext=min(1.0, e * rng.uniform(0.95, 1.0)),
                                        ent=rng.uniform(*ent), her=rng.uniform(*her), dirs=2 + r / 5, cpu=rng.uniform(*cpu) * min(1.0, 0.3 + r / 60),
                                        dw=r * 0.25 * rng.uniform(0.7, 1.3), nc=net * rng.uniform(0.5, 1.5))))

    if family == "fast_encryptor":
        for _ in range(rng.integers(1, 4)):
            out.append(("recon", dict(sc=1 + rng.poisson(2), np=3, cpu=10)))
        in_place = rng.random() < 0.25         # variant that overwrites files in place: no renames
        throttled = rng.random() < 0.2          # a cautious variant that encrypts slowly
        encrypt(int(rng.integers(25, 90)), 12 if throttled else 150, rename_share=(0.02, 0.1) if in_place else (0.7, 1.0), ext=(0.1, 0.3) if in_place else (0.9, 1.0), net=0.5,
                duty=rng.uniform(0.6, 1.0) if throttled else 1.0)
    elif family == "slow_drip":
        for _ in range(rng.integers(5, 16)):
            out.append(("recon", dict(sc=float(rng.poisson(0.4)), np=0.5)))
        encrypt(int(rng.integers(60, 140)), 4, rename_share=(0.3, 1.0), ext=(0.5, 1.0), ent=(7.6, 7.98), her=(0.75, 0.95), cpu=(5, 12), net=0.2, sigma=0.7,
                duty=rng.uniform(0.35, 0.8))
    elif family == "network_spreader":
        for _ in range(rng.integers(3, 11)):
            out.append(("recon", dict(nc=_ln(rng, 40, 0.5), smb=rng.uniform(8, 40), dns=rng.uniform(0.1, 0.8), rare=rng.uniform(5, 20), cpu=8)))
        n = int(rng.integers(25, 70))
        encrypt(n, 25, net=0.0)
        for i in range(n):                     # spreading continues while encrypting
            out[-n + i][1].update(smb=rng.uniform(5, 30), nc=_ln(rng, 25, 0.5), rare=rng.uniform(1, 8), dns=rng.uniform(0, 0.3))
    else:                                       # double_extortion: steal data first, then encrypt
        for _ in range(rng.integers(2, 7)):
            out.append(("recon", dict(sc=float(rng.poisson(1.0)), np=2, rare=rng.uniform(1, 3))))
        for _ in range(rng.integers(10, 41)):
            bo = _ln(rng, 12, 0.6)
            out.append(("exfil", dict(bo=bo, bi=bo / rng.uniform(40, 400), rare=rng.uniform(2, 8), beacon=rng.uniform(0.6, 0.95), nc=rng.uniform(0.5, 3), cpu=10, dw=0.5)))
        encrypt(int(rng.integers(15, 61)), 70, net=0.3)
    return out


def _row(w, run_id, i, family, primary, phase, label, onset):
    r = dict(run_id=run_id, window=i, family=family, benign_profile=primary, phase=phase, label=label, onset=onset)
    r.update(files_modified_per_s=w["fm"], files_renamed_per_s=w["fr"], files_deleted_per_s=w["fd"], ext_change_ratio=w["ext"], write_entropy_mean=w["ent"],
             high_entropy_write_ratio=w["her"], distinct_dirs_touched=w["dirs"], new_process_count=w["np"], suspicious_cmd_count=w["sc"], cpu_percent=w["cpu"],
             disk_write_mb_per_s=w["dw"], new_conn_per_s=w["nc"], smb_distinct_hosts=w["smb"], dns_nxdomain_per_s=w["dns"], bytes_out_mb_per_s=w["bo"],
             out_in_ratio=w["oi"], rare_dest_count=w["rare"], beacon_regularity=w["beacon"])
    return r


def simulate_run(seed, run_id, family="benign"):
    """One virtual machine for 7-20 minutes. Attack runs start normally, then the attack begins."""
    rng = np.random.default_rng(seed)
    host = _host(rng)
    attack = _attack_windows(rng, family) if family != "benign" else []
    onset = int(rng.integers(20, 71)) if attack else -1
    length = onset + len(attack) if attack else int(rng.integers(90, 241))
    length = max(length, 90)
    rows, profile, left, primary = [], None, 0, None
    for i in range(length):
        if left <= 0:
            profile = PROFILES[rng.choice(len(PROFILES), p=_W)]
            left = int(rng.integers(20, 81))
            primary = primary or profile
        left -= 1
        base = benign_window(rng, profile, host)
        if attack and i >= onset and (i - onset) < len(attack):
            phase, contribution = attack[i - onset]
            rows.append(_row(_blend(base, contribution), run_id, i, family, primary, phase, 0 if phase == "sleep" else 1, onset))
        else:
            rows.append(_row(base, run_id, i, family, primary, "benign", 0, onset))
    return rows


def build_dataset(n_benign=500, n_per_family=50, seed=42):
    """A whole labelled data set. Every run is an independent virtual machine, so a
    machine never appears in both the training and the test data."""
    seeds = np.random.SeedSequence(seed).spawn(n_benign + n_per_family * len(FAMILIES))
    plan = ["benign"] * n_benign + [f for f in FAMILIES for _ in range(n_per_family)]
    rows = []
    for k, (family, s) in enumerate(zip(plan, seeds)):
        rows += simulate_run(s, k, family)
    df = pd.DataFrame(rows)
    df[FEATURES] = df[FEATURES].astype("float64")
    return df
