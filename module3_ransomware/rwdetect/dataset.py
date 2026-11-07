import numpy as np
import pandas as pd

from .features import FEATURES
from .simulate import build_dataset  # noqa: F401


def split_runs(df, seed=7, fractions=(0.6, 0.2, 0.2)):
    """Split by whole RUN (never by window), stratified by family, so neighbouring
    windows of one machine can never sit in both training and test data."""
    rng = np.random.default_rng(seed)
    parts = {"train": [], "val": [], "test": []}
    runs = df.groupby("run_id").family.first()
    for family, ids in runs.groupby(runs):
        ids = rng.permutation(ids.index.to_numpy())
        a = int(round(fractions[0] * len(ids)))
        b = a + int(round(fractions[1] * len(ids)))
        parts["train"] += list(ids[:a])
        parts["val"] += list(ids[a:b])
        parts["test"] += list(ids[b:])
    return {name: df[df.run_id.isin(ids)].reset_index(drop=True) for name, ids in parts.items()}


def save_csv(df, path):
    df.to_csv(path, index=False, float_format="%.5g")


def load_csv(path):
    df = pd.read_csv(path)
    missing = [c for c in FEATURES + ["run_id", "window", "family", "label", "onset"] if c not in df.columns]
    if missing:
        raise ValueError(f"The data file is missing columns: {missing}")
    return df
