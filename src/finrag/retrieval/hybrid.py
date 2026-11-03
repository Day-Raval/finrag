"""BM25 keyword search and reciprocal rank fusion with dense search.

BM25 catches exact terms dense embeddings blur: line-item names ("total
assets"), tickers and figures. Its index is built in memory from the
collection's chunk file, using the same text that was embedded.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from rank_bm25 import BM25Okapi

from finrag.indexing.build_index import embed_text
from finrag.retrieval.filters import matches

RRF_K = 60  # standard reciprocal-rank-fusion constant


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+|\d+(?:[.,]\d+)*", text.lower())


@lru_cache(maxsize=2)
def bm25_index(chunks_path: str, header: bool) -> tuple[list[dict], BM25Okapi]:
    chunks = [json.loads(line) for line in Path(chunks_path).read_text().splitlines()]
    return chunks, BM25Okapi([tokens(embed_text(c, header)) for c in chunks])


def bm25_search(question: str, cfg: dict, k: int, flt: dict | None = None) -> list[dict]:
    idx = cfg["index"]
    chunks, bm25 = bm25_index(
        idx["chunks"].format(collection=idx["collection"]),
        cfg["chunking"].get("header", False),
    )
    scores = bm25.get_scores(tokens(question))
    out = []
    for i in sorted(range(len(chunks)), key=lambda i: -scores[i]):
        if matches(chunks[i], flt):
            out.append({**chunks[i], "score": round(float(scores[i]), 4)})
            if len(out) == k:
                break
    return out


def rrf(rankings: list[list[dict]], k: int) -> list[dict]:
    """Merge ranked lists: each chunk scores sum(1 / (60 + rank)) over the lists."""
    fused: dict[str, float] = {}
    chunk_by_id: dict[str, dict] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, 1):
            cid = chunk["chunk_id"]
            fused[cid] = fused.get(cid, 0.0) + 1 / (RRF_K + rank)
            chunk_by_id.setdefault(cid, chunk)
    best = sorted(fused, key=lambda cid: -fused[cid])[:k]
    return [{**chunk_by_id[cid], "score": round(fused[cid], 4)} for cid in best]