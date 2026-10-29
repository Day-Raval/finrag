# Source layout

This directory contains the FinRAG application package. Its README prevents GitHub from collapsing `src` and `finrag` into a single directory label in the repository browser.

The implemented baseline is organized by pipeline stage:

| Package | Module | Responsibility |
| --- | --- | --- |
| `finrag.ingestion` | `fetch_filings.py`, `parse_filings.py` | Download EDGAR filings and parse them into section-level JSONL. |
| `finrag.corpus` | `fixed_chunks.py` | Produce overlapping token chunks with citation metadata. |
| `finrag.embeddings` | `encoder.py` | Load and use the shared local embedding model. |
| `finrag.indexing` | `build_index.py` | Embed chunks and rebuild the local Qdrant index. |
| `finrag.retrieval` | `dense.py` | Retrieve the highest-scoring dense matches. |
| `finrag.generation` | `answer.py` | Format cited context and generate a Groq answer. |
| `finrag.answering` | `pipeline.py`, `run_golden.py` | Run one question or a resumable golden-set benchmark. |
| `finrag.evaluation` | `build_golden.py`, `lookup.py` | Build the golden set and find evidence in parsed filings. |

See the [repository README](../README.md) for setup and runnable commands.

## How it works

The pipeline is file-backed and local through retrieval: raw SEC HTML becomes
parsed JSONL, parsed sections become token-overlapping chunks, chunks become
normalized vectors in local Qdrant, and a question retrieves the nearest chunks.
Only the final grounded answer generation calls Groq. Golden-set runs preserve
the configuration and per-question outputs needed to compare later experiments.

## Limitations

- The package contains a baseline pipeline, not a production service: there is
  no HTTP API, queue, multi-user isolation, or deployment configuration.
- Qdrant runs in local embedded mode, so index access is intended for one local
  process rather than shared concurrent writers.
- Answer judging, hybrid retrieval, reranking, and automated result scoring are
  planned but not implemented.
