"""Shared embedding model, so chunks and questions are embedded the same way."""

from functools import lru_cache

import numpy as np


@lru_cache(maxsize=1)
def get_model(name: str):
    from sentence_transformers import SentenceTransformer  # slow import, load on use

    return SentenceTransformer(name)


def embed(texts: list[str], name: str, progress: bool = False) -> np.ndarray:
    # normalized vectors: cosine similarity == dot product
    return get_model(name).encode(
        texts, batch_size=32, normalize_embeddings=True, show_progress_bar=progress
    )