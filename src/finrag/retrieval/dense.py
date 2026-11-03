"""Dense retrieval: embed the question, return the top-k closest chunks."""

import atexit
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny

from finrag.embeddings.encoder import embed


@lru_cache(maxsize=1)
def get_client(path: str) -> QdrantClient:
    client = QdrantClient(path=path)  # local mode: one open client per process
    atexit.register(client.close)  # close cleanly before interpreter shutdown
    return client


def qdrant_filter(flt: dict | None) -> Filter | None:
    """{"ticker": ["KO"], "fiscal_year": []} -> payload filter; empty lists are ignored."""
    must = [FieldCondition(key=f, match=MatchAny(any=v)) for f, v in (flt or {}).items() if v]
    return Filter(must=must) if must else None


def search(question: str, cfg: dict, k: int | None = None, flt: dict | None = None) -> list[dict]:
    vector = embed([question], cfg["embedding"]["model"])[0]
    hits = get_client(cfg["index"]["qdrant_path"]).query_points(
        cfg["index"]["collection"],
        query=vector.tolist(),
        query_filter=qdrant_filter(flt),
        limit=k or cfg["retrieval"]["top_k"],
    )
    return [{**hit.payload, "score": round(hit.score, 4)} for hit in hits.points]