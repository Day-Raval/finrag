"""Select the 24-question dev subset used for day-to-day experiments.

Run from the repo root:  python -m finrag.evaluation.make_dev

Takes a fixed number of questions per category (seeded, so it is the same
every time) from evals/golden.jsonl and writes evals/dev.jsonl. A dev run
costs ~75K generator tokens instead of ~240K for all 79.
"""

import json
import random
from pathlib import Path

import yaml

PER_CATEGORY = {
    "comparison": 3, "extraction": 4, "multi_year": 3, "numeric": 4,
    "open": 3, "reasoning": 4, "unanswerable": 3,
}  # fmt: skip
SEED = 11


def dev_subset(golden: list[dict]) -> list[dict]:
    rng = random.Random(SEED)
    picked = []
    for cat, n in PER_CATEGORY.items():
        pool = sorted(
            (g for g in golden if g["category"] == cat), key=lambda g: g["id"]
        )
        picked += rng.sample(pool, min(n, len(pool)))
    return sorted(picked, key=lambda g: g["id"])


def main() -> None:
    cfg = yaml.safe_load(Path("config.yaml").read_text())["golden"]
    golden = [json.loads(x) for x in Path(cfg["path"]).read_text().splitlines()]
    dev = dev_subset(golden)
    Path(cfg["dev"]).write_text("".join(json.dumps(g) + "\n" for g in dev))
    print(f"{len(dev)} dev questions -> {cfg['dev']}")


if __name__ == "__main__":
    main()