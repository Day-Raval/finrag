# Generation

This package generates grounded answers with Groq. [`answer.py`](answer.py)
formats every retrieved chunk with a numbered company, fiscal-year, and Item
header, then fills `prompts/answer_v1.md` with that context and the question.

`generate()` uses the configured `openai/gpt-oss-120b` model and returns the
answer plus latency, prompt-token, and completion-token counts. The Groq client
reads `GROQ_API_KEY` from the environment and retries rate-limit and server
errors. The prompt requires source citations and `Not found in the filings.`
when the supplied context lacks support.

[`cache.py`](cache.py) stores every Groq response under `data/cache/llm/`,
keyed by a SHA-256 of the full request: model, prompt (question, retrieved
chunks, and template), and decoding settings. An identical request returns the
saved response with `cached: true` and its original token counts and latency, at
no token cost. Any change to the question, chunks, prompt, model, or settings is
a cache miss. The judge uses the same cache. Delete `data/cache/` to force fresh
calls.

## How it works

`format_context()` labels each retrieved chunk in rank order, then `generate()`
substitutes the resulting context and question into the configured prompt. It
builds the Groq request, returns a cached response when one exists, and
otherwise calls Groq and returns the response with request latency and token
usage. Empty replies are never cached, so they are retried on the next run.

## Limitations

- Citation and no-evidence behavior are prompt instructions; this module does
  not verify that answer citations match retrieved chunks or that calculations
  are correct.
- Generation is constrained by the retrieved top-k context and cannot access a
  filing beyond those chunks.
- A Groq API key and network access are required for uncached requests; only
  rate-limit and server retries are configured.
- The cache assumes a fixed request should give a reusable answer. Groq is not
  perfectly deterministic even at temperature 0, so delete the cache to measure
  run-to-run variation.
- The cache lives under `data/` (gitignored) and grows without limit; a fresh
  clone starts empty.