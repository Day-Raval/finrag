# Retrieval

This package performs dense retrieval over the local Qdrant index.

[`dense.py`](dense.py) embeds a question with the shared embedding model and
returns the closest chunk payloads with rounded similarity scores. It opens one
cached local Qdrant client per process and closes it on interpreter shutdown.

`search(question, cfg)` uses `retrieval.top_k` from `config.yaml` (five in the
baseline); callers can provide `k` to override that count. Hybrid retrieval and
reranking remain disabled in the baseline configuration.

## Results

The checked-in retrieval evaluations measure top-5 search against golden
evidence on all 69 answerable questions:

| Collection | Section recall@5 | Doc recall@5 | MRR |
| --- | ---: | ---: | ---: |
| `fixed_512_64` (baseline) | 0.543 | 0.855 | 0.329 |
| `fixed_512_64_hdr` (best so far) | 0.652 | 0.971 | 0.408 |

Search runs against whichever collection the config names, so an experiment is
evaluated by pointing `FINRAG_CONFIG` at its config file:

```bash
python -m finrag.evaluation.retrieval_eval dense_fixed_512_64
FINRAG_CONFIG=configs/fixed_512_64_hdr.yaml python -m finrag.evaluation.retrieval_eval fixed_512_64_hdr
```

Questions are embedded as plain text; contextual headers are added only to the
indexed chunks.

## How it works

`search()` embeds the question with the same normalized model used for chunks,
queries the configured Qdrant collection, and returns each result's stored
payload with a rounded similarity score. The payload supplies the company,
fiscal year, Item, source URL, and text later used by answer generation.

## Limitations

- Retrieval is dense-only: it has no keyword search, metadata filters, hybrid
  fusion, reranking, or query rewriting.
- There is no relevance-score threshold, so the pipeline always sends up to
  `top_k` matches to generation even for poorly matched questions.
- Search requires a previously built local index and does not detect stale
  chunks when parsed filings or embedding settings change.