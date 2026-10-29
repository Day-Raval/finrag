# Indexing

This package builds the local Qdrant index used by dense retrieval.

[`build_index.py`](build_index.py) reads parsed filings, creates overlapping
chunks, writes them to `data/index/chunks.jsonl`, embeds their text, and rebuilds
the configured Qdrant collection. Each Qdrant payload contains the chunk's
citation metadata and source text.

Run it after fetching and parsing filings:

```bash
python -m finrag.indexing.build_index
```

The builder deletes and recreates the collection on every run; it does not
perform incremental updates.

## How it works

The builder loads `config.yaml`, obtains the embedding model's tokenizer, and
turns every parsed section into chunk records. It saves those records as JSONL
for inspection, embeds their text, recreates the configured Qdrant collection
with cosine distance, and uploads vectors plus metadata in batches of 256. The
final printed count comes from Qdrant after upload.

## Limitations

- Rebuilding deletes the existing collection before loading the new one; retain
  a separate Qdrant path if an earlier index must remain available.
- All chunk records and embeddings are held in memory during a build, which
  limits scalability for a substantially larger corpus.
- This is a local Qdrant index with no incremental updates, payload filtering,
  collection versioning, or index-quality evaluation.
