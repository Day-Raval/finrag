# Changelog

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