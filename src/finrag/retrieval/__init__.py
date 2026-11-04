"""Retrieval entry point: dense search, optionally hybrid, filtered, reranked, covered.

Config `retrieval`: `top_k` results; `hybrid: true` fuses dense and BM25
rankings of `candidates` chunks each; `filter: true` restricts both to the
companies and fiscal years the question names; `rerank: true` reorders
`candidates` first-stage results with the `reranker` cross-encoder;
`decompose: company|filing` gives every named company or filing at least one
result (1.16, needs `filter`).
"""

from finrag.retrieval import dense
from finrag.retrieval.decompose import cover, sub_filters
from finrag.retrieval.filters import matches, question_filter
from finrag.retrieval.hybrid import bm25_search, rrf
from finrag.retrieval.reranker import rerank


def ranked(question: str, cfg: dict, flt: dict | None, k: int) -> list[dict]:
    r = cfg["retrieval"]
    n = r.get("candidates", 50)
    pool = n if r.get("rerank") else k  # the reranker needs a wider pool to reorder
    if r.get("hybrid"):
        hits = rrf([dense.search(question, cfg, n, flt), bm25_search(question, cfg, n, flt)], pool)
    else:
        hits = dense.search(question, cfg, pool, flt)
    return rerank(question, hits, cfg, k) if r.get("rerank") else hits


def search(question: str, cfg: dict) -> list[dict]:
    r = cfg["retrieval"]
    flt = question_filter(question, cfg) if r.get("filter") else None
    hits = ranked(question, cfg, flt, r["top_k"])
    missing = [
        best
        for sub in sub_filters(flt, r.get("decompose"))
        if not any(matches(h, sub) for h in hits)
        for best in ranked(question, cfg, sub, 1)
    ]
    return cover(hits, missing, r["top_k"]) if missing else hits