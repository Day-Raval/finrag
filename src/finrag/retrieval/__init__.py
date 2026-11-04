"""Retrieval entry point: dense search, optionally hybrid, filtered and reranked.

Config `retrieval`: `top_k` results; `hybrid: true` fuses dense and BM25
rankings of `candidates` chunks each (1.13); `filter: true` restricts both to the
companies and fiscal years the question names (1.14); `rerank: true` reorders
`candidates` first-stage results with the `reranker` cross-encoder (1.15).
"""

from finrag.retrieval import dense
from finrag.retrieval.filters import question_filter
from finrag.retrieval.hybrid import bm25_search, rrf
from finrag.retrieval.reranker import rerank


def search(question: str, cfg: dict) -> list[dict]:
    r = cfg["retrieval"]
    flt = question_filter(question, cfg) if r.get("filter") else None
    n = r.get("candidates", 50)
    k = n if r.get("rerank") else r["top_k"]  # the reranker needs a wider pool to reorder
    if r.get("hybrid"):
        hits = rrf([dense.search(question, cfg, n, flt), bm25_search(question, cfg, n, flt)], k)
    else:
        hits = dense.search(question, cfg, k, flt)
    return rerank(question, hits, cfg, r["top_k"]) if r.get("rerank") else hits