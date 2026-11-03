"""Retrieval entry point: dense search, optionally hybrid and filtered search.

Config `retrieval`: `top_k` results; `hybrid: true` fuses dense and BM25
rankings of `candidates` chunks each; `filter: true` restricts both to the
companies and fiscal years the question names.
"""

from finrag.retrieval import dense
from finrag.retrieval.filters import question_filter
from finrag.retrieval.hybrid import bm25_search, rrf


def search(question: str, cfg: dict) -> list[dict]:
    r = cfg["retrieval"]
    flt = question_filter(question, cfg) if r.get("filter") else None
    if not r.get("hybrid"):
        return dense.search(question, cfg, r["top_k"], flt)
    n = r.get("candidates", 50)
    return rrf([dense.search(question, cfg, n, flt), bm25_search(question, cfg, n, flt)], r["top_k"])