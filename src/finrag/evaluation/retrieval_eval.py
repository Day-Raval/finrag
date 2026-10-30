"""Retrieval-only evaluation: search every answerable golden question, no LLM.

Run from the repo root:  python -m finrag.evaluation.retrieval_eval dense_fixed_512_64

Costs zero Groq tokens, so use it for every chunking / search experiment
(steps 1.11-1.15). Saves reports/retrieval/<name>.json.
"""

import json
import sys
from pathlib import Path

import yaml

from finrag.evaluation.score_run import mean
from finrag.evaluation.scorers import retrieval_scores
from finrag.retrieval.dense import search

KEYS = ["section_recall", "doc_recall", "mrr"]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m finrag.evaluation.retrieval_eval <name>")
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    golden = [
        g
        for g in map(json.loads, Path(cfg["golden"]["path"]).read_text().splitlines())
        if g["evidence"]
    ]
    scores = []
    for g in golden:
        s = retrieval_scores(g["evidence"], search(g["question"], cfg))
        scores.append({"id": g["id"], "category": g["category"], **s})

    by_cat = {
        c: {k: mean([s[k] for s in scores if s["category"] == c]) for k in KEYS}
        for c in sorted({s["category"] for s in scores})
    }
    overall = {k: mean([s[k] for s in scores]) for k in KEYS}
    out = Path("reports/retrieval") / f"{sys.argv[1]}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"name": sys.argv[1], "top_k": cfg["retrieval"]["top_k"],
                               "collection": cfg["index"]["collection"], "overall": overall,
                               "by_category": by_cat, "per_question": scores}, indent=2))  # fmt: skip

    print(f"{'category':14}{'n':>4}" + "".join(f"{k:>16}" for k in KEYS))
    for name, s in [*by_cat.items(), ("ALL", overall)]:
        n = len(scores) if name == "ALL" else sum(x["category"] == name for x in scores)
        print(f"{name:14}{n:>4}" + "".join(f"{s[k]:>16}" for k in KEYS))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()