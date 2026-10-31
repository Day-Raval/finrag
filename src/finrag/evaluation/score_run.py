"""Score a saved run with the deterministic scorers (no LLM calls).

Run from the repo root:  python -m finrag.evaluation.score_run baseline

Reads reports/runs/<name>/answers.jsonl, writes scores.jsonl (per question) and
summary.json (overall + by category) next to it, and prints a summary table.
"""

import json
import statistics
import sys
from pathlib import Path

import yaml

from finrag.evaluation.scorers import (
    has_citation,
    numeric_match,
    refused,
    retrieval_scores,
)

METRICS = [
    "section_recall",
    "doc_recall",
    "mrr",
    "numeric_match",
    "citation",
    "refused",
]


def score(row: dict, gold: dict) -> dict:
    answerable = gold["category"] != "unanswerable"
    return {
        "id": row["id"],
        "category": gold["category"],
        **(retrieval_scores(gold["evidence"], row["retrieved"]) or {}),
        "numeric_match": numeric_match(row["answer"], gold["answer"])
        if answerable
        else None,
        "citation": has_citation(row["answer"]) if answerable else None,
        "refused": refused(row["answer"]),
        "total_s": row["total_s"],
        "tokens": row["prompt_tokens"] + row["completion_tokens"],
    }


def mean(values: list) -> float | None:
    values = [float(v) for v in values if v is not None]
    return round(statistics.mean(values), 3) if values else None


def summarize(scores: list[dict]) -> dict:
    out = {"n": len(scores)}
    for m in METRICS:
        out[m] = mean([s.get(m) for s in scores])
    return out


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m finrag.evaluation.score_run <run_name>")
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    run_dir = Path(cfg["runs_dir"]) / sys.argv[1]
    golden = {
        g["id"]: g
        for g in map(json.loads, Path(cfg["golden"]["path"]).read_text().splitlines())
    }
    rows = [
        json.loads(line)
        for line in (run_dir / "answers.jsonl").read_text().splitlines()
    ]
    scores = [score(r, golden[r["id"]]) for r in rows]

    with (run_dir / "scores.jsonl").open("w") as f:
        f.writelines(json.dumps(s) + "\n" for s in scores)

    unanswerable = [s for s in scores if s["category"] == "unanswerable"]
    answerable = [s for s in scores if s["category"] != "unanswerable"]
    latency = sorted(s["total_s"] for s in scores)
    summary = {
        "run": sys.argv[1],
        "answered": len(rows),
        "overall": summarize(answerable),
        "refusal_accuracy": mean([s["refused"] for s in unanswerable]),
        "false_refusal_rate": mean([s["refused"] for s in answerable]),
        "p50_s": round(statistics.median(latency), 1),
        "p95_s": latency[min(len(latency) - 1, int(0.95 * len(latency)))],
        "tokens_per_question": round(statistics.mean(s["tokens"] for s in scores)),
        "by_category": {
            c: summarize([s for s in scores if s["category"] == c])
            for c in sorted({s["category"] for s in scores})
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"run {summary['run']}  ({summary['answered']} answered)\n")
    print(f"{'category':14}{'n':>4}" + "".join(f"{m:>16}" for m in METRICS))
    for name, s in [
        *summary["by_category"].items(),
        ("ANSWERABLE", summary["overall"]),
    ]:
        cells = "".join(f"{'-' if s[m] is None else s[m]:>16}" for m in METRICS)
        print(f"{name:14}{s['n']:>4}{cells}")
    print(
        f"\nrefusal accuracy {summary['refusal_accuracy']} | false refusals "
        f"{summary['false_refusal_rate']} | p50 {summary['p50_s']}s | p95 {summary['p95_s']}s "
        f"| {summary['tokens_per_question']:,} tokens/question"
    )


if __name__ == "__main__":
    main()