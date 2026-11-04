"""Score and rerank first-stage candidates with a local cross-encoder.

A cross-encoder reads the question and a chunk together, so it judges relevance
better than comparing two separately made embeddings, but it is too slow to run
over the whole index. It only reorders the `candidates` search already found.
"""

from functools import lru_cache

from finrag.indexing.build_index import embed_text


@lru_cache(maxsize=1)
def get_model(name: str):
    from sentence_transformers import CrossEncoder  # slow import, load on use

    # shortcut: question + 512-token chunk is cut at 512 tokens, so a chunk's tail
    # is not scored; raise if a reranker with a longer limit is used
    return CrossEncoder(name, max_length=512)


def rerank(question: str, chunks: list[dict], cfg: dict, k: int) -> list[dict]:
    if not chunks:
        return []
    header = cfg["chunking"].get("header", False)
    pairs = [(question, embed_text(c, header)) for c in chunks]
    scores = get_model(cfg["retrieval"]["reranker"]).predict(pairs, batch_size=4)  # fits a 6 GB GPU
    best = sorted(range(len(chunks)), key=lambda i: -scores[i])[:k]
    return [{**chunks[i], "score": round(float(scores[i]), 4)} for i in best]