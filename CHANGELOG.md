# Changelog

## v0.2.0 — Improved retrieval, configured experiments evaluated end to end, web app (2026-11-11)

Every change was measured on the golden set and kept only if it helped;
`reports/ablation.md` records each decision, including the ones dropped.

### Added
- **Contextual chunk headers:** every chunk starts with `company | FY | Item`.
- **Hybrid search:** BM25 + dense, top 50 each, fused by reciprocal rank (k=60).
- **Company/fiscal-year filter:** rule-based, no LLM call.
- **Per-company coverage:** each company named in a question gets a passage.
- **Web app (Annualyst):** FastAPI `/ask`, `/plan`, `/health`, and a research
  workspace that ties every figure in an answer to the filing excerpt it came
  from (found / calculated / not traceable).
- **Evaluation:** 24-question dev subset, run-to-run `diff` with a regression
  gate, ablation table, and CI that re-scores every saved run.
- **Docs:** failure case study (J&J refusal with the evidence in context).

### Measured and dropped
Section-aware chunking, MiniLM and bge cross-encoder rerankers, and prompt
rewrites v2 and v3.

### Final results (full golden set, 79/79 answered; quality on 69 answerable)
Run: `reports/runs/final`, config `configs/hdr_hf_decomp_company.yaml`,
prompt `prompts/answer_v1.md`.

| Metric | v0.1.0 | v0.2.0 |
| --- | ---: | ---: |
| Section recall@5 | 0.543 | 0.804 |
| Document recall@5 | 0.855 | 1.000 |
| MRR | 0.329 | 0.658 |
| Answer correctness (LLM judge) | 0.167 | 0.333 |
| Faithfulness (non-refused answers) | 0.909 (20/22) | 0.805 (33/41) |
| False refusal rate | 0.681 | 0.420 |
| Refusal accuracy (unanswerable) | 1.000 | 0.900 |
| Numeric match | 0.172 | 0.278 |
| Citation rate | 0.333* | 0.667 |
| p50 / p95 latency | 22.8 s / 32.0 s | 23.1 s / 28.8 s |
| Tokens per question | 3,043 | 3,136 |

\*v0.1.0 reported 0.290; the citation scorer now also accepts `FY2022`-style
years and `【】` brackets, and every run was re-scored.

Correctness: 16 answers improved, 2 regressed (fb_01107 correct → partial,
fb_06272 correct → incorrect); the gate passed.

### Known limits
- Faithfulness fell as the system answered more questions; reasoning questions
  are the weakest (4 of 9 faithful).
- 42% of answerable questions are still refused; one unanswerable question was
  answered.
- p95 latency (28.8 s) is far above the 10 s target; it is dominated by the
  generator call on Groq's free tier.

## v0.1.0 — Baseline RAG (2026-10-31)

A deliberately naive RAG over SEC 10-K filings, released as the measured
starting point for every later improvement. Not production-ready.

### What's included
- **Corpus:** 30 10-Ks (15 companies, FY2021–FY2022) fetched from SEC EDGAR and
  parsed into Item sections with column-aligned Markdown tables.
- **Baseline pipeline:** fixed 512-token chunks (64 overlap), local
  `BAAI/bge-small-en-v1.5` embeddings, local Qdrant, top-5 dense retrieval,
  Groq `openai/gpt-oss-120b` for answers.
- **Golden set:** 79 questions (57 FinanceBench + 22 custom) across 7 categories,
  including 10 unanswerable.
- **Evaluation harness:** deterministic scorers (retrieval recall, MRR, numeric
  match, citation, refusal), retrieval-only evaluation with zero LLM calls,
  correctness and faithfulness LLM judges (`gpt-oss-20b`), and judge validation
  against 20 hand labels.

### Baseline results (79/79 answered)
| Metric | Baseline |
| --- | ---: |
| Section recall@5 | 0.543 |
| Document recall@5 | 0.855 |
| MRR | 0.329 |
| Answer correctness (LLM judge, answerable) | 0.167 |
| Faithfulness (non-refused answers) | 0.909 |
| False refusal rate (answerable) | 0.681 |
| Refusal accuracy (unanswerable) | 1.000 |
| Citation rate | 0.290 |
| p50 / p95 latency | 22.8 s / 32.0 s |
| Tokens per question | 3,043 |

**Judge validation:** 90% pass/fail agreement with hand labels, Cohen's kappa
0.74. Both disagreements were the judge being more lenient (accepting wrong
reasoning, and missing a wrong-year answer), so correctness may be slightly
overstated.

### Key findings
- **The baseline refuses far too often rather than hallucinating.** It refused
  68% of answerable questions, yet 91% of the answers it did give were
  supported by context. Of the first 42 false refusals, 21 had the right
  section in context (prompt too strict), 14 had the right filing but wrong
  section, and 7 retrieved the wrong filing.
- **Wrong fiscal year is a recurring failure:** FY2021 and FY2022 chunks look
  alike, so answers cite or compute from the wrong year.
- **Comparison questions** rarely retrieve both companies in the top 5.

### Known limitations
- General Mills FY2022 uses positioned text instead of HTML tables, so its
  tables parse as one cell per line.
- Groq free tier allows ~65 full questions per day on `gpt-oss-120b`.
- Correctness judge never uses the "refused" verdict (scores refusals as
  incorrect; same 0 score).

### Next
Retrieval experiments (structure-aware chunking, hybrid search, metadata
filtering, reranking), then a grounded answer prompt to cut false refusals.