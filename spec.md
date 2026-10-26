# FinRAG — Spec

## User
Financial analyst asking questions about public companies' annual reports.

## Corpus
10-K filings, FY2021 + FY2022, for: AMD, Boeing, American Express, PepsiCo, 3M,
Verizon, CVS Health, AES, Johnson & Johnson, Corning, Lockheed Martin, Coca-Cola,
American Water Works, General Mills, Pfizer (30 filings). Source: SEC EDGAR.

## Quality bar
1. Numbers are correct (within ±1% after rounding) and come from the right company + fiscal year.
2. Every factual claim cites its source (company, year, 10-K section).
3. Calculations show the figures used.
4. Says "not found in the filings" instead of guessing when evidence is missing.
5. p95 latency under 10s; cost tracked per query.

## Stack
- Generation + judge: Groq 
- Embeddings: local sentence-transformers (BAAI/bge-small-en-v1.5)
- Vector store: Qdrant (local)

## Out of scope (v1)
10-Qs, earnings calls, real-time prices, investment advice.
