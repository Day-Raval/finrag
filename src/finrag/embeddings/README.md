# Embeddings

This package embeds filing chunks and user questions with the local
`BAAI/bge-small-en-v1.5` model configured in `config.yaml`.

[`encoder.py`](encoder.py) lazy-loads and caches the `SentenceTransformer` model.
`embed()` encodes text in batches of 32 with normalized vectors, making cosine
similarity equivalent to a dot product. Indexing and retrieval share this module
so chunks and queries use the same model and normalization.

## How it works

`get_model()` creates the `SentenceTransformer` only when first needed and
caches that single instance for the process. `embed()` passes chunk text or
questions to the model's `encode()` method and returns a NumPy array; indexing
enables its progress bar while retrieval does not.

## Limitations

- The model is a general-purpose local model and is not fine-tuned on SEC
  filings or project-specific relevance labels.
- Model download and cache availability are delegated to
  `sentence-transformers`; the first use may require network access.
- The baseline exposes no device, precision, batching, or model-version
  controls beyond the configured model name.
