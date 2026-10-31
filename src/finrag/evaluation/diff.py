"""Compare two scored runs, question by question.

Run from the repo root:  python -m finrag.evaluation.diff baseline exp_hybrid [max_drop]

Needs score_run on both runs; uses judge_correctness.jsonl too when both runs
have it. Compares only the questions both runs answered (so a dev run can be
compared with the full baseline). Exits with code 1 if correctness drops by
more than max_drop (default 0.05), so it can gate CI.
"""

import json
import sys
from pathlib import Path

import yaml

from finrag.evaluation.judge import SCORES
from finrag.evaluation.score_run import mean

# (metric, higher is better)
METRICS = [
    ("correctness", True),
    ("section_recall", True),
    ("doc_recall", True),
    ("mrr", True),
    ("numeric_match", True),
    ("citation", True),
    ("refused", False),  # false refusals: lower is better
]


def load(run_dir: Path) -> dict[str, dict]:
    """Per-question scores, plus the judge's correctness score when present."""
    rows = {
        r["id"]: r
        for r in map(json.loads, (run_dir / "scores.jsonl").read_text().splitlines())
    }
    judge = run_dir / "judge_correctness.jsonl"
    if judge.exists():
        for j in map(json.loads, judge.read_text().splitlines()):
            if j["id"] in rows:
                rows[j["id"]]["correctness"] = SCORES["correctness"].get(j["verdict"])
                rows[j["id"]]["verdict"] = j["verdict"]
    return rows


def compare(a: dict[str, dict], b: dict[str, dict]) -> tuple[dict, list, list]:
    """Metric means over shared answerable questions, then per-question changes."""
    ids = sorted(i for i in a.keys() & b.keys() if a[i]["category"] != "unanswerable")
    table = {
        m: (mean([a[i].get(m) for i in ids]), mean([b[i].get(m) for i in ids]))
        for m, _ in METRICS
    }
    worse = [
        i
        for i in ids
        if (b[i].get("correctness") or 0) < (a[i].get("correctness") or 0)
    ]
    better = [
        i
        for i in ids
        if (b[i].get("correctness") or 0) > (a[i].get("correctness") or 0)
    ]
    return table, worse, better


def main() -> None:
    if len(sys.argv) not in (3, 4):
        raise SystemExit(
            "usage: python -m finrag.evaluation.diff <run_a> <run_b> [max_drop]"
        )
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    name_a, name_b = sys.argv[1], sys.argv[2]
    max_drop = float(sys.argv[3]) if len(sys.argv) == 4 else 0.05
    a, b = (load(Path(cfg["runs_dir"]) / n) for n in (name_a, name_b))
    table, worse, better = compare(a, b)

    shared = len(a.keys() & b.keys())
    print(
        f"{name_a} vs {name_b} on {shared} shared questions (answerable only below)\n"
    )
    print(f"{'metric':16}{name_a:>14}{name_b:>14}{'change':>10}")
    for m, higher_better in METRICS:
        va, vb = table[m]
        if va is None or vb is None:
            print(
                f"{m:16}{'-' if va is None else va:>14}{'-' if vb is None else vb:>14}"
            )
            continue
        delta = round(vb - va, 3)
        tag = (
            ""
            if delta == 0
            else (" better" if (delta > 0) == higher_better else " worse")
        )
        print(f"{m:16}{va:>14}{vb:>14}{delta:>+10}{tag}")

    for label, ids in (("Regressions", worse), ("Improvements", better)):
        print(f"\n{label} ({len(ids)}):")
        for i in ids:
            print(
                f"  {i:9} {a[i].get('verdict', '?'):10} -> {b[i].get('verdict', '?')}"
            )

    va, vb = table["correctness"]
    if va is None or vb is None:
        print(
            "\nNo judge verdicts in both runs: run the correctness judge to gate on quality."
        )
        return
    if vb < va - max_drop:
        print(f"\nFAIL: correctness dropped {va - vb:.3f} (> {max_drop})")
        sys.exit(1)
    print(f"\nOK: correctness did not drop by more than {max_drop}")


if __name__ == "__main__":
    main()