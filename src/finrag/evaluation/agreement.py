"""Shows how often the LLM judge agrees with your hand labels?

Run from the repo root:  python -m finrag.evaluation.agreement baseline

Compares reports/runs/<run>/human_labels.jsonl with judge_correctness.jsonl.
Agreement and Cohen's kappa use pass/fail (pass = "correct"), since the judge
and a person may split partial/incorrect/refused differently for the same fail.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import yaml

LABELS = ["correct", "partial", "incorrect", "refused"]


def cohens_kappa(a: list, b: list) -> float:
    """Agreement corrected for chance: 1 = perfect, 0 = no better than chance."""
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in ca.keys() | cb.keys()) / n**2
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m finrag.evaluation.agreement <run>")
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    run_dir = Path(cfg["runs_dir"]) / sys.argv[1]
    load = lambda name: {
        r["id"]: r for r in map(json.loads, (run_dir / name).read_text().splitlines())
    }
    human, judge = load("human_labels.jsonl"), load("judge_correctness.jsonl")
    ids = sorted(human.keys() & judge.keys())
    h = [human[i]["label"] for i in ids]
    j = [judge[i]["verdict"] for i in ids]
    h_pass, j_pass = [x == "correct" for x in h], [x == "correct" for x in j]

    agree = sum(x == y for x, y in zip(h_pass, j_pass)) / len(ids)
    kappa = cohens_kappa(h_pass, j_pass)
    print(f"{len(ids)} answers | pass/fail agreement {agree:.0%} | Cohen's kappa {kappa:.2f} | "
          f"exact 4-way agreement {sum(x == y for x, y in zip(h, j)) / len(ids):.0%}\n")  # fmt: skip

    print("rows = you, columns = judge")
    print(f"{'':11}" + "".join(f"{c:>11}" for c in LABELS))
    for r in LABELS:
        print(
            f"{r:11}"
            + "".join(
                f"{sum(x == r and y == c for x, y in zip(h, j)):>11}" for c in LABELS
            )
        )

    print("\nPass/fail disagreements:")
    for i, hp, jp in zip(ids, h_pass, j_pass):
        if hp != jp:
            print(
                f"  {i:9} you={human[i]['label']:9} judge={judge[i]['verdict']:9} | judge: {judge[i].get('reason', '')[:90]}"
            )
            if human[i]["note"]:
                print(f"  {'':9} your note: {human[i]['note'][:110]}")
    target = agree >= 0.8 and kappa >= 0.6
    print(
        f"\n{'PASS' if target else 'BELOW TARGET'}: target is agreement >= 80% and kappa >= 0.6"
    )


if __name__ == "__main__":
    main()