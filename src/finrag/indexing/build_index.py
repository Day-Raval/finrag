"""Chunk parsed filings, embed them, and load them into local Qdrant.

Uses `chunking` from the config (config.yaml, or an experiment file chosen with
FINRAG_CONFIG): strategy `fixed` (step 1.6) or `section` (step 1.11), and
`header: true` to embed each chunk with a company / fiscal year / Item header
(step 1.12). Rebuilds only the configured collection, so
other experiments' collections stay available. Also writes every chunk to
data/index/<collection>.jsonl (used by the faithfulness judge and debugging).
"""

import json
import time
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from finrag.config import load_config
from finrag.corpus.fixed_chunks import fixed_token_chunks, iter_chunks
from finrag.corpus.section_chunks import section_token_chunks
from finrag.embeddings.encoder import embed, get_model

BATCH = 256


def embed_text(chunk: dict, header: bool) -> str:
    """Step 1.12: optionally prefix the chunk with where it came from."""
    if not header:
        return chunk["text"]
    title = f": {chunk['title']}" if chunk["title"] else ""
    return f"{chunk['company']} | FY{chunk['fiscal_year']} | Item {chunk['item']}{title}\n{chunk['text']}"


def main() -> None:
    cfg = load_config()
    model_name, idx = cfg["embedding"]["model"], cfg["index"]
    start = time.time()

    tokenizer = get_model(model_name).tokenizer
    ch = cfg["chunking"]
    if ch["strategy"] == "fixed":
        split = lambda t: fixed_token_chunks(t, tokenizer, ch["size"], ch["overlap"])
    elif ch["strategy"] == "section":
        split = lambda t: section_token_chunks(t, tokenizer, ch["size"])
    else:
        raise SystemExit(
            f"unknown chunking strategy: {ch['strategy']!r} (fixed|section)"
        )
    chunks = list(iter_chunks(cfg["corpus"]["parsed_dir"], split))
    chunks_path = Path(idx["chunks"].format(collection=idx["collection"]))
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    with chunks_path.open("w") as f:
        f.writelines(json.dumps(c) + "\n" for c in chunks)
    print(f"{len(chunks):,} chunks -> {chunks_path}  ({time.time() - start:.0f}s)")

    header = ch.get("header", False)
    vectors = embed([embed_text(c, header) for c in chunks], model_name, progress=True)
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