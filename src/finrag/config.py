"""Load config.yaml, optionally overlaid with an experiment config.

config.yaml is the baseline. To run an experiment, point FINRAG_CONFIG at a
file in configs/ that sets only the keys that differ (for example `chunking`
and `index.collection`); every other setting still comes from config.yaml:

    FINRAG_CONFIG=configs/section_512.yaml python -m finrag.indexing.build_index
"""

import os
from pathlib import Path

import yaml


def merge(base: dict, override: dict) -> dict:
    """Nested dicts merge key by key; any other value in `override` replaces."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            out[key] = merge(base[key], value)
        else:
            out[key] = value
    return out


def load_config() -> dict:
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    if experiment := os.getenv("FINRAG_CONFIG"):
        cfg = merge(cfg, yaml.safe_load(Path(experiment).read_text()) or {})
        cfg["experiment"] = experiment  # recorded in each run's config snapshot
    return cfg