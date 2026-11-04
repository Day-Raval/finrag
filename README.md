# Annualyst

*Grounded Q&A over SEC 10-K filings, with an evaluation harness. Repository and Python package: `finrag`. Latest release: [v0.1.0](https://github.com/Day-Raval/finrag/releases/tag/v0.1.0).*

**Annualyst** is a retrieval-augmented generation (RAG) system for answering financial-analysis questions from public companies' annual reports. It is designed to ground every answer in SEC 10-K filings, cite the source of each factual claim, and state when the available filings do not contain the answer.

> **Project status:** v0.1.0 baseline RAG is implemented, evaluated, and released. The pipeline parses SEC filings, creates fixed-size chunks, embeds and indexes them locally, retrieves the top five matching chunks, and generates grounded answers with Groq. A 79-question golden set, deterministic scoring, and an LLM judge validated against hand labels measure the baseline. Since v0.1.0 the repository also has experiment tooling (a 24-question dev subset, an LLM response cache, a run-to-run diff, and per-experiment config overrides), and retrieval experiments: a contextual chunk header, hybrid BM25 + dense search, a company/fiscal-year filter, and per-company coverage raised section recall from 0.543 to 0.804, doc recall to 1.0, and MRR from 0.329 to 0.658. On the dev subset this nearly doubled judged correctness (0.214 to 0.381) and cut false refusals from 0.619 to 0.381, with no regressions. Refusals with the right filing already in context remain the main gap; the system is not production-ready.

## What it is for

Annualyst is built for financial analysts who need answers from a bounded filing corpus rather than general web knowledge. The initial corpus covers FY2021 and FY2022 10-K filings for 15 public companies (30 filings total), sourced from SEC EDGAR:

AMD, Boeing, American Express, PepsiCo, 3M, Verizon, CVS Health, AES, Johnson & Johnson, Corning, Lockheed Martin, Coca-Cola, American Water Works, General Mills, and Pfizer.

The v1 scope excludes 10-Qs, earnings calls, real-time prices, and investment advice.

## Design principles

- **Grounded answers:** answer only from retrieved filing context.
- **Traceable claims:** cite facts as `[company, year, section]`.
- **Numerical integrity:** use figures from the correct company and fiscal year; calculations should show their inputs.
- **Explicit uncertainty:** return `Not found in the filings.` instead of guessing when evidence is unavailable.
- **Operational discipline:** target p95 query latency below 10 seconds and track cost per query.

## Intended architecture

| Layer | v1 technology | Configuration |
| --- | --- | --- |
| Corpus | SEC EDGAR 10-K filings | `data/manifest.csv` |
| Chunking | Fixed-size chunks (512 tokens, 64-token overlap) | `config.yaml` |
| Embeddings | Local `BAAI/bge-small-en-v1.5` | `config.yaml` |
| Vector search | Local Qdrant | `config.yaml` |
| Answer generation | Groq `openai/gpt-oss-120b` | `config.yaml` |
| Answer evaluation | Deterministic scorers and Groq `openai/gpt-oss-20b` judge | `config.yaml` |

This table is the v0.1.0 baseline. Experiments change one layer at a time through files in [`configs/`](configs/); see [Retrieval experiments](#retrieval-experiments) for results.

The answer prompt at [`prompts/answer_v1.md`](prompts/answer_v1.md) enforces source citations and the required no-evidence response.

```mermaid
flowchart LR
    analyst[Financial analyst] --> question[Question]
    question --> retrieve[Retrieve relevant chunks]
    filings[(SEC 10-K filings)] --> ingest[Ingest and chunk]
    ingest --> embed[Create embeddings]
    embed --> qdrant[(Qdrant vector store)]
    retrieve <--> qdrant
    retrieve --> context[Grounded filing context]
    context --> generate[Groq answer generation]
    question --> generate
    generate --> answer[Answer with citations]
    answer --> judge[Groq quality judge]
    judge --> response[Validated analyst response]

    config[config.yaml] -. configures .-> ingest
    config -. configures .-> retrieve
    config -. configures .-> generate
    config -. configures .-> judge
```

The implemented baseline follows the complete flow, including deterministic scoring and the Groq quality judge. Components under `src/finrag` are organized around these pipeline responsibilities.

## Getting started

### Prerequisites

- Python 3.12 or later
- A [Groq API key](https://console.groq.com/keys)
- An SEC-compliant User-Agent containing your name and email address

### Install

```bash
git clone https://github.com/Day-Raval/finrag.git
cd finrag
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Configure credentials

```bash
cp .env.example .env
```

Set the following values in `.env`:

```dotenv
GROQ_API_KEY=your_groq_api_key
SEC_USER_AGENT="Your Name your.email@example.com"
```

`.env` is ignored by Git. Never commit API keys or personal contact details.

### Validate the local setup

```bash
pytest
```

The tests cover configuration loading and experiment overrides, environment setup, filing fetching and parsing, fixed-size and section-aware chunking, contextual chunk headers, deterministic scoring, judge-output parsing, judge-agreement statistics, the dev subset, the LLM response cache, run comparison, citation-context formatting, and golden-set construction. All tests run offline: they do not contact SEC EDGAR or Groq.

### Build the local RAG corpus

With `SEC_USER_AGENT` set in `.env`, run these commands from the repository root:

```bash
python -m finrag.ingestion.fetch_filings
python -m finrag.ingestion.parse_filings
python -m finrag.indexing.build_index
```

The fetcher retrieves the configured FY2021 and FY2022 10-Ks for 15 companies (30 filings), skips amendments, respects SEC request limits, and writes filing metadata and SHA-256 checksums to `data/manifest.csv`. Fiscal years are based on the filing period end, with first-week-of-January ends assigned to the prior fiscal year for 52/53-week companies. Existing raw filings are skipped on reruns.

The parser writes one JSONL record per 10-K Item under `data/parsed/`, including a `COVER` section for cover-page facts, preserving section metadata and formatting tables as Markdown. Its report flags filings that need review before downstream processing. The index builder tokenizes each parsed section into overlapping 512-token chunks, embeds them with `BAAI/bge-small-en-v1.5`, writes the chunks to `data/index/<collection>.jsonl`, and rebuilds the local Qdrant collection. All generated files under `data/` are gitignored; see [`src/finrag/ingestion/README.md`](src/finrag/ingestion/README.md) for parsing details, output fields, and known filing quirks.

### Ask a question

After building the index, query the baseline pipeline with a Groq API key configured:

```bash
python -m finrag.answering.pipeline "What was 3M's FY2022 revenue?"
```

The command retrieves the top five dense matches from the local Qdrant index, sends their citation-labeled text to the configured Groq model, and prints the answer, retrieved chunk IDs and scores, latency, and token usage.

### Create and run the golden set

Build the golden set after parsing filings:

```bash
python -m finrag.evaluation.build_golden
```

This downloads and caches FinanceBench's open sample in `data/financebench/`, selects in-scope 10-K questions, maps their evidence to parsed filing sections, and combines them with the project's custom cases. The resulting `evals/golden.jsonl` contains 57 FinanceBench and 22 custom questions across extraction, numeric, reasoning, open, comparison, multi-year, and unanswerable categories.

To run every golden question through the current pipeline:

```bash
python -m finrag.answering.run_golden baseline
```

Results and a copy of the active configuration are written to `reports/runs/baseline/`. Interrupted or rate-limited runs are resumable: rerun the same command to skip completed questions.

Score the saved answers and run the judge:

```bash
python -m finrag.evaluation.score_run baseline
python -m finrag.evaluation.retrieval_eval dense_fixed_512_64
python -m finrag.evaluation.judge baseline correctness
python -m finrag.evaluation.judge baseline faithfulness
```

`score_run` writes per-question scores and `summary.json`; `retrieval_eval` writes retrieval-only metrics without generating answers. The judge writes one JSONL result per mode, skips completed verdicts, and retries invalid prior verdicts. Correctness compares an answer with its reference; faithfulness checks non-refused answers against their retrieved context.

### Validate the judge

Before trusting judge scores, compare them with your own labels on a fixed sample of 20 answers (16 attempted answers and 4 refusals):

```bash
python -m finrag.evaluation.label baseline       # interactive; the judge's verdicts are hidden
python -m finrag.evaluation.agreement baseline   # agreement, Cohen's kappa, disagreements
```

Labels are saved to `reports/runs/<run>/human_labels.jsonl` after every answer, so labelling can be stopped and resumed. The target is at least 80% pass/fail agreement and kappa of at least 0.6.

### Run experiments cheaply

Groq's free tier allows about 200K tokens per model per day, and a full 79-question run uses about 240K. Day-to-day experiments therefore use a fixed 24-question dev subset (3–4 questions per category, about 72K tokens), and the full golden set is kept for milestone runs:

```bash
python -m finrag.evaluation.make_dev                 # writes evals/dev.jsonl (fixed seed)
python -m finrag.answering.run_golden my_exp dev     # answer the dev subset
python -m finrag.evaluation.score_run my_exp
python -m finrag.evaluation.judge my_exp correctness
python -m finrag.evaluation.diff dev_baseline my_exp # what improved, what regressed
```

Every Groq call (answers and judge verdicts) is cached under `data/cache/llm/`, keyed by model, full prompt, and decoding settings. Rerunning an unchanged configuration therefore costs no tokens, and an experiment only pays for questions whose prompt actually changed. Empty answers and unparseable judge replies are never cached. `diff` compares only the questions both runs answered and exits with code 1 if judged correctness drops by more than 0.05, so it can gate CI. Retrieval-only experiments need no LLM at all: use `retrieval_eval`.

## Baseline results

The checked-in `baseline` run answered all 79 golden questions. Its retrieval-only results for fixed 512-token chunks, 64-token overlap, and top-5 dense search were:

| Metric | Result |
| --- | ---: |
| Section recall | 54.3% |
| Document recall | 85.5% |
| MRR | 0.329 |

For the 69 answerable questions, deterministic scoring found a 17.2% numeric-match rate, 29.0% citation rate, and 68.1% false-refusal rate. The 10 unanswerable cases were refused correctly. Median latency was 22.8 seconds and p95 was 32.01 seconds, which is above the project target.

The LLM judge marked 20 answers correct, 3 partial, and 56 incorrect (0.272 weighted correctness). Of 22 non-refused answers evaluated for faithfulness, 20 were faithful and 2 unfaithful (0.909). These baseline measurements identify retrieval coverage, answer completeness, and refusal behavior as the next improvement areas rather than claims of system quality. The 0.272 correctness figure covers all 79 questions; on the 69 answerable ones it is 0.167. The correctness judge was validated against 20 hand-labelled answers: 90% pass/fail agreement, Cohen's kappa 0.74. Both disagreements were the judge being more lenient than the human label, so correctness may be slightly overstated.

On the 24-question dev subset, the checked-in `dev_baseline` run scored 0.214 judged correctness and a 0.619 false-refusal rate on the 21 answerable questions. Comparing it with the original baseline answers to the same questions showed that fresh answers changed in only one place (one answer dropped its citation), so on the dev subset a change of about 0.05 (one question) is within run-to-run noise.

See [CHANGELOG.md](CHANGELOG.md) for the failure breakdown and known limitations.

## Retrieval experiments

Each experiment changes one setting on top of the baseline and is scored with `retrieval_eval` on all 69 answerable golden questions (top-5, no LLM calls). Retrieval is deterministic, but one question is worth about 0.015, so differences under about 0.03 are treated as ties.

| Experiment | Config | Section recall@5 | Doc recall@5 | MRR |
| --- | --- | ---: | ---: | ---: |
| Baseline: fixed 512 tokens, 64 overlap | `config.yaml` | 0.543 | 0.855 | 0.329 |
| Section-aware chunks, 512 tokens (1.11) | [`section_512`](configs/section_512.yaml) | 0.522 | 0.848 | 0.343 |
| Section-aware chunks, 256 tokens (1.11) | [`section_256`](configs/section_256.yaml) | 0.551 | 0.841 | 0.341 |
| Section-aware 512 + contextual header | [`section_512_hdr`](configs/section_512_hdr.yaml) | 0.551 | 0.928 | 0.361 |
| Fixed 512/64 + contextual header (1.12) | [`fixed_512_64_hdr`](configs/fixed_512_64_hdr.yaml) | 0.652 | 0.971 | 0.408 |
| Header + hybrid BM25/dense (1.13) | [`hdr_hybrid`](configs/hdr_hybrid.yaml) | 0.623 | 0.884 | 0.434 |
| Header + company/year filter (1.14) | [`hdr_filter`](configs/hdr_filter.yaml) | 0.739 | 0.978 | 0.545 |
| Header + hybrid + filter (1.13 + 1.14) | [`hdr_hybrid_filter`](configs/hdr_hybrid_filter.yaml) | 0.797 | 0.986 | 0.658 |
| + MiniLM cross-encoder rerank (1.15) | [`hdr_hf_rerank`](configs/hdr_hf_rerank.yaml) | 0.783 | 0.986 | 0.624 |
| + bge-reranker-base rerank (1.15) | [`hdr_hf_rerank_bge`](configs/hdr_hf_rerank_bge.yaml) | 0.812 | 0.978 | 0.538 |
| **+ per-company coverage (1.16)** | [`hdr_hf_decomp_company`](configs/hdr_hf_decomp_company.yaml) | **0.804** | **1.000** | **0.658** |
| + per-filing coverage (1.16) | [`hdr_hf_decomp_filing`](configs/hdr_hf_decomp_filing.yaml) | 0.804 | 1.000 | 0.658 |

- **Contextual header: clear win.** Embedding each chunk as `company | FY | Item: title` plus its text raised section recall by 0.109 and doc recall to 0.971, so the right company and fiscal year are now almost always retrieved. It is built from existing metadata and costs no LLM tokens.
- **Section-aware chunking: no gain.** Keeping paragraphs and table rows intact tied the baseline at both sizes and weakened the header's effect. A likely cause is that section chunks have no overlap, so content near a boundary appears in only one chunk.
- **Hybrid search alone: worse.** Fusing BM25 with dense search (reciprocal rank fusion over 50 candidates each) lowered doc recall to 0.884: 10-Ks share the same vocabulary ("total assets", "net revenue"), so keyword matches pull in other companies' filings. MRR still rose slightly.
- **Company/fiscal-year filter: the biggest single gain.** Rules read the company names and fiscal years a question mentions (`FY22`, `FY 2021`, `JnJ`, `AMEX`) and restrict search to those filings, falling back to unfiltered search when a question names none. On the golden set it narrows all 69 answerable questions without excluding any gold evidence filing.
- **Hybrid + filter: best so far.** With the filter removing other companies' chunks, BM25's exact-term matching finds the right section within the right filing: section recall +0.145 and MRR +0.25 over the header alone, so the evidence usually ranks first or second.
- **Cross-encoder reranking: no gain, kept off.** Reranking the 50 hybrid + filter candidates helped prose questions (bge raised reasoning section recall from 0.75 to 0.94) but misranked Markdown tables (extraction MRR fell from 0.79 to 0.46), so overall MRR dropped with both rerankers. bge also added about 2.4 s at p95 on an RTX 4050 GPU (34 s on CPU). Section recall@3 (0.717 vs 0.797 at five) kept the answer prompt at five chunks.
- **Per-company coverage: closes the comparison gap.** When a question names several companies and one has no chunk in the top five, that company's best chunk replaces the fifth result. A forced split was avoided because only 9 of the 20 golden questions that name two filings need evidence from both: a 10-K also reports the prior year. Comparison doc recall rose from 0.833 to 1.0 with every other category unchanged; splitting by filing (company x year) added nothing. `hdr_hf_decomp_company` is the current best configuration.

### Answer quality after the retrieval steps

The dev subset was answered with `hdr_hf_decomp_company` and judged like the baseline (21 answerable questions; the run is in [`reports/runs/dev_retrieval`](reports/runs/dev_retrieval)). The prompt and models are unchanged, so the difference comes from retrieval alone.

| Dev subset | `dev_baseline` | `dev_retrieval` | Change |
| --- | ---: | ---: | ---: |
| Judged correctness | 0.214 | 0.381 | +0.167 |
| False-refusal rate | 0.619 | 0.381 | -0.238 |
| Citation rate | 0.286 | 0.571 | +0.285 |
| Numeric match | 0.259 | 0.389 | +0.130 |
| Faithfulness (non-refused) | — | 0.923 | |
| p95 latency | 32.0 s | 28.1 s | |
| Tokens per question | 3,043 | 3,098 | |

`diff` found five improved answers and no regressions. With every evidence filing now retrieved, 8 of 21 answerable questions are still refused and comparison questions score 0.167, so the next step is the answer prompt rather than retrieval.

## Repository layout

```text
.
├── config.yaml              # Baseline RAG, model, chunking, golden-set, and index configuration
├── configs/                 # Experiment overrides (FINRAG_CONFIG=configs/<name>.yaml)
├── prompts/
│   ├── answer_v1.md              # Grounded-answer prompt contract
│   ├── judge_correctness_v1.md   # Correctness judge rubric
│   └── judge_faithfulness_v1.md  # Faithfulness judge rubric
├── src/
│   ├── README.md            # Source layout note
│   └── finrag/
│       ├── config.py             # Loads config.yaml + optional experiment override
│       ├── ingestion/
│       │   ├── fetch_filings.py  # EDGAR 10-K downloader
│       │   └── parse_filings.py  # Section-level JSONL parser
│       ├── corpus/
│       │   ├── fixed_chunks.py   # Overlapping token chunker
│       │   └── section_chunks.py # Paragraph/table-aware chunker
│       ├── embeddings/
│       │   └── encoder.py        # Shared local embedding model
│       ├── indexing/
│       │   └── build_index.py    # Local Qdrant index builder
│       ├── retrieval/
│       │   ├── __init__.py       # search(): dense, optionally hybrid, filtered, reranked, covered
│       │   ├── dense.py          # Dense Qdrant retrieval with payload filter
│       │   ├── hybrid.py         # BM25 search and reciprocal rank fusion
│       │   ├── filters.py        # Company / fiscal-year extraction from questions
│       │   ├── reranker.py       # Optional cross-encoder reranking (off by default)
│       │   └── decompose.py      # Per-company coverage for multi-company questions
│       ├── generation/
│       │   ├── answer.py         # Grounded Groq answer generation
│       │   └── cache.py          # Disk cache for LLM calls
│       ├── answering/
│       │   ├── pipeline.py       # Single-question RAG pipeline
│       │   └── run_golden.py     # Resumable golden/dev-set runner
│       ├── evaluation/
│       │   ├── build_golden.py   # FinanceBench/custom golden-set builder
│       │   ├── make_dev.py       # 24-question dev subset
│       │   ├── lookup.py         # Parsed-filing lookup CLI
│       │   ├── scorers.py        # Deterministic scorers
│       │   ├── score_run.py      # Deterministic saved-run scoring
│       │   ├── retrieval_eval.py # Retrieval-only benchmarking
│       │   ├── judge.py          # Correctness and faithfulness judge
│       │   ├── label.py          # Blind hand-labelling CLI
│       │   ├── agreement.py      # Judge-vs-human agreement and kappa
│       │   └── diff.py           # Run-to-run comparison and CI gate
│       └── __init__.py      # Application package
├── evals/
│   ├── custom.jsonl         # Hand-written golden cases
│   ├── golden.jsonl         # Generated FinanceBench and custom cases
│   └── dev.jsonl            # 24-question dev subset
├── reports/
│   ├── runs/                # Per-run answers, scores, judge verdicts, hand labels, config
│   └── retrieval/           # Retrieval-only results, one JSON per experiment
├── tests/                   # Offline tests (no SEC or Groq calls)
├── .env.example             # Required environment-variable template
├── CHANGELOG.md             # Release notes
├── LICENSE                  # MIT
└── spec.md                  # Product scope and quality bar
```

## Configuration

Runtime behavior is centralized in [`config.yaml`](config.yaml):

- `corpus`: filing years and manifest location
- `chunking`: chunk strategy (`fixed` or `section`), size, overlap, and contextual `header`
- `embedding`: embedding provider and model
- `retrieval`: result count (`top_k`), hybrid BM25 + dense fusion (`hybrid`, `candidates`), company/fiscal-year filtering (`filter`), cross-encoder reranking (`rerank`, `reranker`), and per-company coverage (`decompose`)
- `generation` and `judge`: Groq models and decoding settings
- `golden`: golden-set, custom-case, dev-subset, and FinanceBench cache locations
- `index`: local chunk export and Qdrant collection settings
- `runs_dir`: benchmark-output directory

`config.yaml` is the baseline. Each experiment is a small file in [`configs/`](configs/) that overrides only the keys it changes, selected with the `FINRAG_CONFIG` environment variable:

```bash
FINRAG_CONFIG=configs/section_512.yaml python -m finrag.indexing.build_index
FINRAG_CONFIG=configs/section_512.yaml python -m finrag.evaluation.retrieval_eval section_512

# retrieval-only experiments reuse an existing index: no rebuild
FINRAG_CONFIG=configs/hdr_hybrid_filter.yaml python -m finrag.evaluation.retrieval_eval hdr_hybrid_filter
```

Every module reads the merged configuration, and `run_golden` saves it with each run, so a run's `config.yaml` snapshot records exactly which experiment produced it. An experiment that changes chunking names its own `index.collection` after its file, so its Qdrant collection and `data/index/<collection>.jsonl` chunk file sit beside the baseline's instead of replacing them. An experiment that changes only retrieval (the `hdr_*` files) reuses an existing collection with identical chunking settings, which `tests/test_config.py` checks.

## Quality contract

An answer is considered acceptable only when it:

1. Uses the correct company and fiscal year, with values accurate to within ±1% after rounding.
2. Cites every factual claim with the company, year, and 10-K section.
3. Shows inputs for derived calculations.
4. Does not fabricate evidence when the corpus has no supporting passage.

See [`spec.md`](spec.md) for the full v1 requirements.

## Development

Run the test suite before submitting changes:

```bash
pytest
```

Dependencies are listed in [`requirements.txt`](requirements.txt). The project currently uses a `src/` package layout and requires Python 3.12+.

### Package boundaries

The source package is separated by pipeline stage:

| Package | Responsibility |
| --- | --- |
| `finrag.ingestion` | Download and parse SEC filings into section-level JSONL. |
| `finrag.config` | Load `config.yaml` merged with an optional experiment override. |
| `finrag.corpus` | Create fixed-token or section-aware chunks while preserving citation metadata. |
| `finrag.embeddings` | Load and use the shared embedding model for chunks and questions. |
| `finrag.indexing` | Embed chunks and rebuild the local Qdrant collection. |
| `finrag.retrieval` | Return the top matches: dense, optionally fused with BM25, filtered to the companies and years a question names, reranked, and covering every named company. |
| `finrag.generation` | Format cited context, call the Groq answer model, and cache LLM responses. |
| `finrag.answering` | Orchestrate a question, the golden set, or the dev subset through retrieval and generation. |
| `finrag.evaluation` | Build the golden and dev sets, score and compare runs, benchmark retrieval, judge answers, and validate the judge against hand labels. |

## Security and data handling

- Treat `.env` as sensitive and keep it local.
- Use a truthful, contactable SEC User-Agent when downloading filings.
- Keep source filings and manifests reproducible; do not present retrieved content as real-time market data.
- Annualyst is an analytical research tool, not investment advice.

## License

Code is released under the [MIT License](LICENSE).

The 57 FinanceBench questions in `evals/golden.jsonl` (ids starting `fb_`) come from
[FinanceBench](https://huggingface.co/datasets/PatronusAI/financebench) by Patronus AI
(Islam et al., 2023, arXiv:2311.11944) and remain under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/): non-commercial use
with attribution. SEC filings are public documents and are not redistributed here;
`fetch_filings` downloads them from EDGAR.