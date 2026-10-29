"""Question -> retrieve -> generate. Also a one-question CLI.

Run from the repo root:  python -m finrag.answering.pipeline "What was 3M's FY2022 revenue?"
"""

import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from finrag.generation.answer import generate
from finrag.retrieval.dense import search


def answer(question: str, cfg: dict) -> dict:
    start = time.time()
    chunks = search(question, cfg)
    retrieve_s = round(time.time() - start, 2)
    result = generate(question, chunks, cfg)
    return {
        **result,
        "retrieve_s": retrieve_s,
        "total_s": round(time.time() - start, 2),
        "retrieved": [
            {k: c[k] for k in ("chunk_id", "doc_id", "item", "score")} for c in chunks
        ],
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit('usage: python -m finrag.answering.pipeline "your question"')
    load_dotenv()
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    out = answer(sys.argv[1], cfg)
    print(out["answer"], "\n")
    for r in out["retrieved"]:
        print(f"  {r['score']:.3f}  {r['chunk_id']}")
    print(
        f"\n{out['total_s']}s, {out['prompt_tokens']} prompt + {out['completion_tokens']} completion tokens"
    )


if __name__ == "__main__":
    main()