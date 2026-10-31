# Source layout

This directory contains the Annualyst application package. Its README prevents GitHub from collapsing `src` and `finrag` into a single directory label in the repository browser.

The implemented baseline is organized by pipeline stage:

| Package | Module | Responsibility |
| --- | --- | --- |
| `finrag.ingestion` | `fetch_filings.py`, `parse_filings.py` | Download EDGAR filings and parse them into section-level JSONL. |
| `finrag.corpus` | `fixed_chunks.py` | Produce overlapping token chunks with citation metadata. |
| `finrag.embeddings` | `encoder.py` | Load and use the shared local embedding model. |
| `finrag.indexing` | `build_index.py` | Embed chunks and rebuild the local Qdrant index. |
| `finrag.retrieval` | `dense.py` | Retrieve the highest-scoring dense matches. |
| `finrag.generation` | `answer.py`, `cache.py` | Format cited context, generate a Groq answer, and cache LLM responses on disk. |
| `finrag.answering` | `pipeline.py`, `run_golden.py` | Run one question, or a resumable benchmark over the golden set or dev subset. |
| `finrag.evaluation` | `build_golden.py`, `make_dev.py`, `lookup.py`, `scorers.py`, `score_run.py`, `retrieval_eval.py`, `judge.py`, `label.py`, `agreement.py`, `diff.py` | Build the golden and dev sets, score and compare runs, benchmark retrieval, judge answers, and validate the judge. |

See the [repository README](../README.md) for setup and runnable commands.

## How it works

The pipeline is file-backed and local through retrieval: raw SEC HTML becomes
parsed JSONL, parsed sections become token-overlapping chunks, chunks become
normalized vectors in local Qdrant, and a question retrieves the nearest chunks.
Answer generation and optional LLM judging call Groq, and every Groq response is
cached on disk so an unchanged request is never paid for twice. Golden-set and
dev-subset runs preserve the configuration and per-question outputs needed to
compare later experiments; deterministic scoring, retrieval-only evaluation, and
`diff` turn those outputs into reproducible comparisons.

## Limitations

- The package contains a baseline pipeline, not a production service: there is
  no HTTP API, queue, multi-user isolation, or deployment configuration.
- Qdrant runs in local embedded mode, so index access is intended for one local
  process rather than shared concurrent writers.
- Hybrid retrieval, metadata filtering, and reranking are not implemented yet.
- The LLM judge evaluates saved answers after a run; it is not part of the
  interactive answer path and its verdicts should be treated as evaluation
  signals rather than ground truth.