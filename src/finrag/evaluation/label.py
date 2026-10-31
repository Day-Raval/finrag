"""hand-label a sample of a run's answers, blind to the judge.

Run from the repo root:  python -m finrag.evaluation.label baseline

Shows each sampled answer next to its reference and asks for your verdict.
Saves after every label to reports/runs/<run>/human_labels.jsonl, so you can
quit (Ctrl+C) and rerun to continue. The judge's verdicts are never shown.
"""

import json
import random
import sys
import textwrap
from pathlib import Path

import yaml

from finrag.evaluation.scorers import refused

KEYS = {"c": "correct", "p": "partial", "i": "incorrect", "r": "refused"}
SEED = 7  # fixed, so the sample is the same every time


def sample(answers: list[dict], n_answered: int = 16, n_refused: int = 4) -> list[dict]:
    """Mostly real attempts (where judging is hard), plus a few refusals.

    Unanswerable questions are left out: their verdict is never in doubt.
    """
    rng = random.Random(SEED)
    pool = [a for a in answers if a["category"] != "unanswerable"]
    tried = [a for a in pool if not refused(a["answer"])]
    gave_up = [a for a in pool if refused(a["answer"])]
    picked = rng.sample(tried, min(n_answered, len(tried)))
    picked += rng.sample(gave_up, min(n_refused, len(gave_up)))
    return sorted(picked, key=lambda a: a["id"])


def show(a: dict, n: int, total: int) -> None:
    wrap = lambda s: textwrap.fill(s, 100, subsequent_indent="    ")
    print(f"\n{'=' * 100}\n[{n}/{total}] {a['id']}  ({a['category']})\n")
    print(wrap(f"Q:  {a['question']}") + "\n")
    print(wrap(f"REFERENCE:  {a['reference']}") + "\n")
    print(f"ANSWER:\n{a['answer']}\n")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m finrag.evaluation.label <run>")
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    run_dir = Path(cfg["runs_dir"]) / sys.argv[1]
    answers = [
        json.loads(x) for x in (run_dir / "answers.jsonl").read_text().splitlines()
    ]
    out = run_dir / "human_labels.jsonl"
    done = (
        {json.loads(x)["id"] for x in out.read_text().splitlines()}
        if out.exists()
        else set()
    )
    todo = [a for a in sample(answers) if a["id"] not in done]
    print(
        f"{len(done)} labeled, {len(todo)} to go. Keys: c=correct p=partial i=incorrect r=refused"
    )

    with out.open("a") as f:
        for n, a in enumerate(todo, len(done) + 1):
            show(a, n, len(done) + len(todo))
            key = ""
            while key not in KEYS:
                key = input("verdict [c/p/i/r]: ").strip().lower()
            note = input("one-line reason (optional): ").strip()
            f.write(json.dumps({"id": a["id"], "category": a["category"],
                                "label": KEYS[key], "note": note}) + "\n")  # fmt: skip
            f.flush()
    print(f"\nDone -> {out}\nNext: python -m finrag.evaluation.agreement {sys.argv[1]}")


if __name__ == "__main__":
    main()