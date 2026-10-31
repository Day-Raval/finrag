"""Self-contained LLM-as-judge on a saved run (gpt-oss-20b on Groq).

Run from the repo root:
  python -m finrag.evaluation.judge baseline correctness    # every question, ~1-2K tokens each
  python -m finrag.evaluation.judge baseline faithfulness   # non-refused answers only, ~4K each

Writes reports/runs/<run>/judge_<kind>.jsonl. Rerunnable: questions already
judged are skipped (failed parses are retried), so a run stopped by the daily
token limit resumes where it stopped.
"""

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import groq
import yaml
from dotenv import load_dotenv

from finrag.evaluation.score_run import mean
from finrag.generation import cache
from finrag.generation.answer import format_context, get_client

SCORES = {
    "correctness": {"correct": 1.0, "partial": 0.5, "incorrect": 0.0, "refused": 0.0},
    "faithfulness": {"faithful": 1.0, "unfaithful": 0.0},
}
PASSTHROUGH = ("temperature", "reasoning_effort", "max_tokens")


def fill(template: str, **fields: str) -> str:
    # str.replace, not str.format: the rubric's JSON example contains braces
    for key, value in fields.items():
        template = template.replace("{" + key + "}", value)
    return template


def parse(text: str | None, kind: str) -> dict:
    """The judge's JSON verdict, or verdict 'error' if it is missing or invalid."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    try:
        out = json.loads(match.group()) if match else {}
    except json.JSONDecodeError:
        out = {}
    if not isinstance(out, dict) or out.get("verdict") not in SCORES[kind]:
        return {"verdict": "error", "raw": (text or "")[:300]}
    return out


def ask(prompt: str, judge: dict, kind: str) -> tuple[str, int]:
    """Judge reply and tokens spent (0 when served from the cache)."""
    request = {
        "model": judge["model"],
        "messages": [{"role": "user", "content": prompt}],
        **{k: judge[k] for k in PASSTHROUGH if k in judge},
    }
    hit = cache.get(request)
    if hit:
        return hit["content"], 0
    while True:
        try:
            resp = get_client().chat.completions.create(**request)
            break
        except groq.RateLimitError as e:
            if "per day" in str(e) or "TPD" in str(e):
                raise
            time.sleep(20)  # per-minute limit: wait for the window to roll over
    content = resp.choices[0].message.content
    # cache only valid verdicts, so bad replies are retried next run
    if parse(content, kind)["verdict"] != "error":
        cache.put(request, {"content": content})
    return content, resp.usage.total_tokens

def main() -> None:
    if len(sys.argv) != 3 or sys.argv[2] not in SCORES:
        raise SystemExit(
            "usage: python -m finrag.evaluation.judge <run> correctness|faithfulness"
        )
    run, kind = sys.argv[1], sys.argv[2]
    load_dotenv()
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    run_dir = Path(cfg["runs_dir"]) / run
    template = Path(cfg["judge"][f"{kind}_prompt"]).read_text()
    answers = [
        json.loads(line)
        for line in (run_dir / "answers.jsonl").read_text().splitlines()
    ]

    if kind == "faithfulness":
        answers = [a for a in answers if not refused(a["answer"])]  # nothing to check
        # shortcut: chunk text comes from the current index; judge a run before re-indexing
        lines = Path(cfg["index"]["chunks"]).read_text().splitlines()
        chunks = {c["chunk_id"]: c for c in map(json.loads, lines)}

    out = run_dir / f"judge_{kind}.jsonl"
    judged = (
        {r["id"]: r for r in map(json.loads, out.read_text().splitlines())}
        if out.exists()
        else {}
    )
    todo = [
        a for a in answers if judged.get(a["id"], {}).get("verdict", "error") == "error"
    ]
    print(f"{len(answers) - len(todo)} already judged, {len(todo)} to go -> {out}")

    with out.open("a") as f:
        for n, a in enumerate(todo, 1):
            fields = {
                "question": a["question"],
                "reference": a["reference"],
                "answer": a["answer"],
            }
            if kind == "faithfulness":
                fields["context"] = format_context(
                    [chunks[r["chunk_id"]] for r in a["retrieved"]]
                )
            try:
                text, tokens = ask(fill(template, **fields), cfg["judge"], kind)
            except groq.RateLimitError as e:
                print(
                    f"\nDaily token limit reached after {n - 1}; rerun later to resume.\n{e}"
                )
                break
            row = {
                "id": a["id"],
                "category": a["category"],
                **parse(text, kind),
                "tokens": tokens,
            }
            f.write(json.dumps(row) + "\n")
            f.flush()
            judged[a["id"]] = row
            print(f"[{n}/{len(todo)}] {a['id']:9} {row['verdict']}")

    rows = [judged[a["id"]] for a in answers if a["id"] in judged]

    def score(rs: list[dict]) -> float | None:
        return mean([SCORES[kind].get(r["verdict"]) for r in rs])

    print(
        f"\n{kind}: {len(rows)}/{len(answers)} judged | verdicts {dict(Counter(r['verdict'] for r in rows))}"
    )
    for c in sorted({r["category"] for r in rows}):
        print(f"  {c:14} {score([r for r in rows if r['category'] == c])}")
    answerable = [r for r in rows if r["category"] != "unanswerable"]
    print(
        f"  {'ANSWERABLE':14} {score(answerable)}  | {sum(r['tokens'] for r in rows):,} tokens"
    )


if __name__ == "__main__":
    main()