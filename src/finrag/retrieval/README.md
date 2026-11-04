# Retrieval

This package returns the chunks a question is answered from: dense search,
optionally fused with BM25 keyword search (step 1.13), filtered to the companies
and fiscal years the question names (1.14), reranked by a cross-encoder (1.15),
and topped up so every company the question names is represented (1.16).

| Module | Responsibility |
| --- | --- |
| [`__init__.py`](__init__.py) | `search(question, cfg)`: the entry point used by answering and evaluation. |
| [`dense.py`](dense.py) | Embed the question and query local Qdrant, with an optional payload filter. |
| [`hybrid.py`](hybrid.py) | In-memory BM25 over the collection's chunk file, and reciprocal rank fusion. |
| [`filters.py`](filters.py) | Read tickers and fiscal years from the question with rules (no LLM). |
| [`reranker.py`](reranker.py) | Optional local cross-encoder that reorders first-stage candidates. |
| [`decompose.py`](decompose.py) | Per-company (or per-filing) coverage for questions naming several. |

`search()` reads the `retrieval` section of the merged config:

| Key | Default | Effect |
| --- | --- | --- |
| `top_k` | 5 | Number of chunks returned. |
| `hybrid` | false | Fuse dense and BM25 rankings with reciprocal rank fusion. |
| `candidates` | 50 | Chunks each ranker contributes before fusion, and the rerank pool. |
| `filter` | false | Restrict search to the companies and years in the question. |
| `rerank` | false | Reorder `candidates` results with the `reranker` cross-encoder. |
| `reranker` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model name. |
| `decompose` | false | `company` or `filing`: every named company (or filing) gets at least one result. Needs `filter`. |

## Results

Top-5 search against golden evidence on all 69 answerable questions:

| Config | Section recall@5 | Doc recall@5 | MRR | Section recall@3 | Search p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `config.yaml` (baseline, dense) | 0.543 | 0.855 | 0.329 | | |
| `fixed_512_64_hdr` (contextual header) | 0.652 | 0.971 | 0.408 | | |
| `hdr_hybrid` (+ BM25 fusion) | 0.623 | 0.884 | 0.434 | | |
| `hdr_filter` (+ company/year filter) | 0.739 | 0.978 | 0.545 | | |
| `hdr_hybrid_filter` (hybrid + filter) | 0.797 | 0.986 | 0.658 | 0.717 | 0.53 s |
| `hdr_hf_rerank` (+ MiniLM rerank) | 0.783 | 0.986 | 0.624 | 0.717 | 0.80 s |
| `hdr_hf_rerank_bge` (+ bge-reranker-base, GPU) | 0.812 | 0.978 | 0.538 | 0.667 | 2.94 s |
| `hdr_hf_decomp_company` (best so far) | **0.804** | **1.000** | **0.658** | 0.717 | 0.57 s |
| `hdr_hf_decomp_filing` | 0.804 | 1.000 | 0.658 | 0.717 | 0.78 s |

- Hybrid search alone pulls in other companies' filings, because 10-Ks share
  the same vocabulary; with the filter applied first, BM25's exact-term matching
  finds the right section inside the right filing.
- Both rerankers help prose questions but misrank Markdown tables, so MRR falls
  and reranking stays off.
- Per-company coverage raised comparison doc recall from 0.833 to 1.0 without
  changing any other category.

These configs only change retrieval, so they reuse the `fixed_512_64_hdr` index
without a rebuild:

```bash
FINRAG_CONFIG=configs/hdr_hf_decomp_company.yaml python -m finrag.evaluation.retrieval_eval hdr_hf_decomp_company
```

## How it works

- **Dense:** the question is embedded with the same normalized model as the
  chunks (contextual headers are added only to chunks), and Qdrant returns the
  closest chunk payloads with rounded similarity scores. One cached local Qdrant
  client is opened per process and closed on shutdown.
- **Filter:** `question_filter()` matches whole-word company aliases (`Coca
  Cola`, `JnJ`, `AMEX`, ...) and years written as `FY2022`, `FY 22`, `FY'22`, or
  `2022`, keeping only tickers and years in the corpus. An empty field means no
  filter on it, so a question naming no known company or year searches
  everything. Dense search applies the filter as a Qdrant payload condition;
  BM25 applies the same check to its ranked list.
- **BM25:** built lazily from `data/index/<collection>.jsonl`, using the same
  text that was embedded (including the header when enabled), and cached for
  the process. Tokens are lowercase words and numbers.
- **Fusion:** each chunk scores the sum of `1 / (60 + rank)` over the rankings
  it appears in.
- **Rerank:** when enabled, the first stage returns `candidates` chunks and the
  cross-encoder scores each (question, header + chunk) pair, cut at 512 tokens.
- **Coverage:** when the filter names several companies and one has no chunk in
  the results, a search restricted to that company supplies its best chunk,
  which replaces the lowest-ranked result. It does not force an even split:
  most two-year questions are answered from one 10-K, which also reports the
  prior year.

## Limitations

- Company names come from a fixed alias list in `filters.py`; a ticker added to
  the corpus needs its names added there.
- Coverage swaps in one chunk per missing company from the bottom of the list,
  so with three or more companies a company's only chunk can be the one dropped.
- The tested cross-encoders were trained on prose passages and misrank Markdown
  tables; bge-reranker-base also needs a GPU to stay under a few seconds.
- There is no query rewriting or relevance-score threshold, so up to `top_k`
  chunks are always sent to generation, even for poorly matched questions.
- The first hybrid query in a process builds the BM25 index in memory (a few
  seconds for ~8K chunks).
- Search requires a previously built local index and does not detect stale
  chunks when parsed filings or embedding settings change.