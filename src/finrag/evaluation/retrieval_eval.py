"""Retrieval-only evaluation: search every answerable golden question, no LLM.

Costs zero Groq tokens, so use it for every chunking / search experiment.
Saves reports/retrieval/<name>.json with recall@5, MRR, section recall@3 (what a
top-3 prompt would see) and per-question search latency.
"""

import json
import statistics
import sys
import time
from pathlib import Path

from finrag.config import load_config
from finrag.evaluation.score_run import mean
from finrag.evaluation.scorers import retrieval_scores
from finrag.retrieval import search

KEYS = ["section_recall", "doc_recall", "mrr", "section_recall@3"]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m finrag.evaluation.retrieval_eval <name>")
    cfg = load_config()
    golden = [
        g
        for g in map(json.loads, Path(cfg["golden"]["path"]).read_text().splitlines())
        if g["evidence"]
    ]
    search(golden[0]["question"], cfg)  # warm-up: model loads are not query latency
    scores, latency = [], []
    for g in golden:
        start = time.perf_counter()
        hits = search(g["question"], cfg)
        latency.append(time.perf_counter() - start)
        s = retrieval_scores(g["evidence"], hits)
        s["section_recall@3"] = retrieval_scores(g["evidence"], hits[:3])["section_recall"]
        scores.append({"id": g["id"], "category": g["category"], **s})

    by_cat = {
        c: {k: mean([s[k] for s in scores if s["category"] == c]) for k in KEYS}
        for c in sorted({s["category"] for s in scores})
    }
    overall = {k: mean([s[k] for s in scores]) for k in KEYS}
    latency.sort()
    timing = {
        "p50_s": round(statistics.median(latency), 3),
        "p95_s": round(latency[min(len(latency) - 1, int(0.95 * len(latency)))], 3),
    }
    out = Path("reports/retrieval") / f"{sys.argv[1]}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"name": sys.argv[1], "top_k": cfg["retrieval"]["top_k"],
                               "collection": cfg["index"]["collection"], "overall": overall,
                               **timing, "by_category": by_cat, "per_question": scores}, indent=2))  # fmt: skip

    print(f"{'category':14}{'n':>4}" + "".join(f"{k:>18}" for k in KEYS))
    for name, s in [*by_cat.items(), ("ALL", overall)]:
        n = len(scores) if name == "ALL" else sum(x["category"] == name for x in scores)
        print(f"{name:14}{n:>4}" + "".join(f"{s[k]:>18}" for k in KEYS))
    print(f"\nsearch latency p50 {timing['p50_s']}s | p95 {timing['p95_s']}s\n-> {out}")


if __name__ == "__main__":
    main()