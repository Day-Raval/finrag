# Indexing

This package builds the local Qdrant collections used by dense retrieval.

[`build_index.py`](build_index.py) reads parsed filings, chunks them with the
configured strategy, writes the chunks to `data/index/<collection>.jsonl`,
embeds them, and rebuilds the configured Qdrant collection. Each Qdrant payload
holds the chunk's citation metadata and source text.

```bash
python -m finrag.indexing.build_index                                               # baseline
FINRAG_CONFIG=configs/fixed_512_64_hdr.yaml python -m finrag.indexing.build_index   # an experiment
```

Settings come from the merged config (`config.yaml` plus an optional
`FINRAG_CONFIG` override):

| Setting | Effect |
| --- | --- |
| `chunking.strategy` | `fixed` or `section` (see [`../corpus/`](../corpus/README.md)) |
| `chunking.size`, `chunking.overlap` | Chunk size in tokens; overlap applies to `fixed` only |
| `chunking.header` | `true` embeds each chunk as `company \| FY<year> \| Item <n>: <title>` plus its text (step 1.12) |
| `index.collection` | Qdrant collection to rebuild; also names the chunk file |

Each experiment uses its own collection, so collections sit side by side in one
Qdrant store and a rebuild replaces only the configured one.

## How it works

The builder loads the merged config, gets the embedding model's tokenizer, and
turns every parsed section into chunk records with the chosen strategy. It saves
the records as JSONL (the faithfulness judge reads chunk text from this file),
builds the text to embed (with or without the contextual header), embeds it,
recreates the collection with cosine distance, and uploads vectors plus metadata
in batches of 256. The final count comes from Qdrant after upload.

The header is only embedded, not stored in the chunk text, because answer
generation already labels every chunk with its company, fiscal year, and Item.

## Result

The contextual header was the largest retrieval gain so far: on fixed 512/64
chunks it raised section recall@5 from 0.543 to 0.652, document recall from
0.855 to 0.971, and MRR from 0.329 to 0.408, at no LLM cost.

## Limitations

- A rebuild deletes and recreates the configured collection; there are no
  incremental updates.
- All chunk records and embeddings are held in memory during a build, which
  limits scalability for a substantially larger corpus.
- Changing chunking settings without changing `index.collection` overwrites the
  previous index under the same name; keep one collection per experiment.
- There is no Qdrant payload index or index-quality check at build time;
  retrieval filters on the stored `ticker` and `fiscal_year` payload fields by
  scanning, which is fine at this corpus size.