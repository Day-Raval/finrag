"""Step 1.6: chunk parsed filings, embed them, and load them into local Qdrant.

Run from the repo root:  python -m finrag.indexing.build_index

Rebuilds the collection from scratch. Also writes every chunk to
data/index/chunks.jsonl (used later for keyword search and debugging).
"""

import json
import time
from pathlib import Path

import yaml
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from finrag.corpus.fixed_chunks import iter_chunks
from finrag.embeddings.encoder import embed, get_model

BATCH = 256


def main() -> None:
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    model_name, idx = cfg["embedding"]["model"], cfg["index"]
    start = time.time()

    tokenizer = get_model(model_name).tokenizer
    chunks = list(
        iter_chunks(
            cfg["corpus"]["parsed_dir"],
            tokenizer,
            cfg["chunking"]["size"],
            cfg["chunking"]["overlap"],
        )
    )
    Path(idx["chunks"]).parent.mkdir(parents=True, exist_ok=True)
    with open(idx["chunks"], "w") as f:
        f.writelines(json.dumps(c) + "\n" for c in chunks)
    print(f"{len(chunks):,} chunks -> {idx['chunks']}  ({time.time() - start:.0f}s)")

    vectors = embed([c["text"] for c in chunks], model_name, progress=True)
    print(f"embedded {len(vectors):,} chunks ({time.time() - start:.0f}s)")

    client = QdrantClient(path=idx["qdrant_path"])
    if client.collection_exists(idx["collection"]):
        client.delete_collection(idx["collection"])
    client.create_collection(
        idx["collection"],
        vectors_config=VectorParams(size=vectors.shape[1], distance=Distance.COSINE),
    )
    for i in range(0, len(chunks), BATCH):
        client.upsert(
            idx["collection"],
            points=[
                PointStruct(id=j, vector=vectors[j].tolist(), payload=chunks[j])
                for j in range(i, min(i + BATCH, len(chunks)))
            ],
        )
    count = client.count(idx["collection"]).count
    client.close()
    print(
        f"indexed {count:,} chunks in '{idx['collection']}' ({time.time() - start:.0f}s)"
    )


if __name__ == "__main__":
    main()