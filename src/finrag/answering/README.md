# Answering

This package runs the baseline retrieval-to-answer pipeline.

[`pipeline.py`](pipeline.py) retrieves dense matches, generates a grounded Groq
answer, and returns timing, token usage, and retrieved chunk IDs. Query one
question after building the index:

```bash
python -m finrag.answering.pipeline "What was 3M's FY2022 revenue?"
```

[`run_golden.py`](run_golden.py) runs every case in `evals/golden.jsonl`, or
the 24-question dev subset in `evals/dev.jsonl`, and writes `answers.jsonl` plus
a copy of `config.yaml` to `reports/runs/<run_name>/`. Existing answer IDs are
skipped, so a rate-limited or interrupted run resumes when rerun with the same
name:

```bash
python -m finrag.answering.run_golden baseline        # all 79 golden questions
python -m finrag.answering.run_golden my_exp dev      # 24-question dev subset (~72K tokens)
```

Answers served from the LLM response cache are marked `(cached)`, and the final
line reports both the run's total tokens and the tokens actually spent, so an
unchanged rerun shows `0 actually spent`.

The prompt requires `Not found in the filings.` when retrieved context does not
support an answer.

Score a completed run with:

```bash
python -m finrag.evaluation.score_run baseline
```

This writes `scores.jsonl` and `summary.json` alongside the answer rows. Use
the evaluation package's judge command for LLM correctness and faithfulness
verdicts.

## How it works

`answer()` measures retrieval time, calls dense retrieval, passes the returned
chunks to generation, and combines the answer metrics with compact retrieved
chunk identifiers and scores. Its `total_s` is retrieval time plus generation
latency; for a cached answer the original generation latency is kept, so
p50/p95 stay comparable across runs. The single-question CLI loads `.env` and
`config.yaml` before printing that result. The golden runner reads unfinished
case IDs from its output file, answers only remaining cases, and flushes each
new JSONL row so it can resume after interruption.

## Limitations

- The pipeline does not validate model citations, numerical claims, or whether
  retrieved chunks actually support the answer.
- Golden runs catch and resume only `Groq` rate-limit errors; other failures
  stop the run and require investigation before retrying.
- The runner does not score or judge answers itself; run the evaluation commands
  after it completes.
- The first question of each run includes the one-time embedding-model load in
  its retrieval time, which slightly inflates that question's latency.