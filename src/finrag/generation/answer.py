"""Grounded answer generation with Groq, from retrieved chunks."""

import time
from functools import lru_cache
from pathlib import Path

from groq import Groq

PASSTHROUGH = ("temperature", "reasoning_effort", "max_tokens")


@lru_cache(maxsize=1)
def get_client() -> Groq:
    return Groq(max_retries=3)  # reads GROQ_API_KEY; retries 429/5xx with backoff


def format_context(chunks: list[dict]) -> str:
    """Each chunk gets a citation header the prompt asks the model to reuse."""
    return "\n\n".join(
        f"[{n}] {c['company']} | FY{c['fiscal_year']} | Item {c['item']}\n{c['text']}"
        for n, c in enumerate(chunks, 1)
    )


def generate(question: str, chunks: list[dict], cfg: dict) -> dict:
    gen = cfg["generation"]
    prompt = (
        Path(gen["prompt"])
        .read_text()
        .format(context=format_context(chunks), question=question)
    )
    start = time.time()
    resp = get_client().chat.completions.create(
        model=gen["model"],
        messages=[{"role": "user", "content": prompt}],
        **{k: gen[k] for k in PASSTHROUGH if k in gen},
    )
    return {
        "answer": resp.choices[0].message.content,
        "latency_s": round(time.time() - start, 2),
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }