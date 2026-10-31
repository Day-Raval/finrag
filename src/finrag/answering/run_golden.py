"""Answer every golden question with the current config and save the run.

Run from the repo root:
  python -m finrag.answering.run_golden baseline        # all 79 golden questions
  python -m finrag.answering.run_golden exp_hybrid dev  # 24-question dev subset

Writes reports/runs/<name>/answers.jsonl (one line per question) plus a copy of
config.yaml. Rerunnable: questions already answered in that run are skipped, so
a run cut short by Groq rate limits picks up where it stopped.
"""

import json
import shutil
import statistics
import sys
from pathlib import Path

import groq
import yaml
from dotenv import load_dotenv

from finrag.answering.pipeline import answer


def main() -> None:
    if len(sys.argv) not in (2, 3) or sys.argv[2:] not in ([], ["golden"], ["dev"]):
        raise SystemExit(
            "usage: python -m finrag.answering.run_golden <run_name> [golden|dev]"
        )
    question_set = sys.argv[2] if len(sys.argv) == 3 else "golden"
    load_dotenv()
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    run_dir = Path(cfg["runs_dir"]) / sys.argv[1]
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy("config.yaml", run_dir / "config.yaml")
    out_path = run_dir / "answers.jsonl"

    done = (
        {json.loads(line)["id"] for line in out_path.open()}
        if out_path.exists()
        else set()
    )
    golden = [
        json.loads(line)
        for line in Path(cfg["golden"]["dev" if question_set == "dev" else "path"])
        .read_text()
        .splitlines()
    ]
    todo = [g for g in golden if g["id"] not in done]
    print(f"{len(done)} already answered, {len(todo)} to go -> {out_path}")

    with out_path.open("a") as f:
        for n, g in enumerate(todo, 1):
            try:
                result = answer(g["question"], cfg)
            except groq.RateLimitError as e:
                print(
                    f"\nRate limited after {n - 1} new answers; rerun later to resume.\n{e}"
                )
                break
            f.write(json.dumps({"id": g["id"], "category": g["category"], "question": g["question"],
                                "reference": g["answer"], **result}) + "\n")  # fmt: skip
            f.flush()  # keep finished answers if the run is interrupted
            hit = " (cached)" if result["cached"] else ""
            print(f"[{n}/{len(todo)}] {g['id']}  {result['total_s']}s{hit}")

    rows = [json.loads(line) for line in out_path.open()]
    if len(rows) >= 2:
        lat = sorted(r["total_s"] for r in rows)
        p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))]
        tokens = sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows)
        spent = sum(
            r["prompt_tokens"] + r["completion_tokens"]
            for r in rows
            if not r.get("cached")
        )
        print(f"\n{len(rows)}/{len(golden)} answered ({question_set}) | p50 {statistics.median(lat):.1f}s "
              f"| p95 {p95:.1f}s | {tokens:,} tokens total, {spent:,} actually spent")  # fmt: skip


if __name__ == "__main__":
    main()