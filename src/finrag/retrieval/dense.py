"""Dense retrieval: embed the question, return the top-k closest chunks."""

import atexit
from functools import lru_cache

from qdrant_client import QdrantClient

from finrag.embeddings.encoder import embed


@lru_cache(maxsize=1)
def get_client(path: str) -> QdrantClient:
    client = QdrantClient(path=path)  # local mode: one open client per process
    atexit.register(client.close)  # close cleanly before interpreter shutdown
    return client


def search(question: str, cfg: dict, k: int | None = None) -> list[dict]:
    vector = embed([question], cfg["embedding"]["model"])[0]
    hits = get_client(cfg["index"]["qdrant_path"]).query_points(
        cfg["index"]["collection"],
        query=vector.tolist(),
        limit=k or cfg["retrieval"]["top_k"],
    )
    return [{**hit.payload, "score": round(hit.score, 4)} for hit in hits.points]