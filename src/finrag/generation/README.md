# Generation

This package generates grounded answers with Groq. [`answer.py`](answer.py)
formats every retrieved chunk with a numbered company, fiscal-year, and Item
header, then fills `prompts/answer_v1.md` with that context and the question.

`generate()` uses the configured `openai/gpt-oss-120b` model and returns the
answer plus latency, prompt-token, and completion-token counts. The Groq client
reads `GROQ_API_KEY` from the environment and retries rate-limit and server
errors. The prompt requires source citations and `Not found in the filings.`
when the supplied context lacks support.

## How it works

`format_context()` labels each retrieved chunk in rank order, then `generate()`
substitutes the resulting context and question into the configured prompt. It
passes configured decoding settings to Groq and returns the model response with
request latency and token usage for later analysis.

## Limitations

- Citation and no-evidence behavior are prompt instructions; this module does
  not verify that answer citations match retrieved chunks or that calculations
  are correct.
- Generation is constrained by the retrieved top-k context and cannot access a
  filing beyond those chunks.
- A Groq API key and network access are required; only rate-limit and server
  retries are configured.
