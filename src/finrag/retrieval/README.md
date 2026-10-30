# Retrieval

This package performs dense retrieval over the local Qdrant index.

[`dense.py`](dense.py) embeds a question with the shared embedding model and
returns the closest chunk payloads with rounded similarity scores. It opens one
cached local Qdrant client per process and closes it on interpreter shutdown.

`search(question, cfg)` uses `retrieval.top_k` from `config.yaml` (five in the
baseline); callers can provide `k` to override that count. Hybrid retrieval and
reranking remain disabled in the baseline configuration.

## Baseline result

The checked-in `dense_fixed_512_64` retrieval evaluation measures the configured
top-5 search against golden evidence: section recall is 0.543, document recall
is 0.855, and MRR is 0.329. Recreate that measurement after building the index:

```bash
python -m finrag.evaluation.retrieval_eval dense_fixed_512_64
```

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
