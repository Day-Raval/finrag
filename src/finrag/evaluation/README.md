# Evaluation

This package builds the baseline golden set and evaluates saved answer runs.

[`build_golden.py`](build_golden.py) downloads and caches FinanceBench's open
sample, keeps in-scope 10-K questions for the configured companies and years,
maps evidence passages to parsed filing Items, and appends
`evals/custom.jsonl`. It writes `evals/golden.jsonl`, currently containing 57
FinanceBench and 22 custom cases across all baseline categories:

```bash
python -m finrag.evaluation.build_golden
```

[`lookup.py`](lookup.py) searches a parsed filing line by line while authoring
custom cases:

```bash
python -m finrag.evaluation.lookup KO_2022 "total assets"
```

[`make_dev.py`](make_dev.py) picks a fixed 24-question dev subset (3–4 per
category, seeded) for day-to-day experiments, so each one costs about 72K
generator tokens instead of about 240K:

```bash
python -m finrag.evaluation.make_dev    # writes evals/dev.jsonl
```

Golden-set and dev-subset runs are performed by
[`finrag.answering.run_golden`](../answering/run_golden.py).

## Score a run

After running the golden set, calculate deterministic answer and retrieval
metrics without additional model calls:

```bash
python -m finrag.evaluation.score_run baseline
python -m finrag.evaluation.retrieval_eval dense_fixed_512_64
```

`score_run` writes `scores.jsonl` and `summary.json` under
`reports/runs/<run>/`. It reports evidence-section and document recall, MRR,
numeric matching within 1%, citation presence, refusal behavior, latency, and
tokens. `retrieval_eval` writes the same retrieval metrics for answerable
questions to `reports/retrieval/<name>.json`.

The checked-in `baseline` result answered 79/79 cases. Dense top-5 retrieval
with fixed 512-token chunks and 64-token overlap achieved 0.543 section recall,
0.855 document recall, and 0.329 MRR. Among 69 answerable questions,
deterministic scoring recorded 0.172 numeric match, 0.290 citation rate, and
0.681 false-refusal rate; all 10 unanswerable questions were refused.

## Judge a run

Use the configured Groq judge after deterministic scoring:

```bash
python -m finrag.evaluation.judge baseline correctness
python -m finrag.evaluation.judge baseline faithfulness
```

Correctness compares each answer with its reference. Faithfulness checks only
non-refused answers against the chunks retrieved for that answer. Each command
writes `judge_<kind>.jsonl`, resumes completed work, and retries invalid prior
judge output. Valid verdicts are cached, so rejudging an unchanged answer costs
no tokens. The checked-in baseline has 20 correct, 3 partial, and 56
incorrect correctness verdicts (0.272 weighted score); its faithfulness judge
found 20 faithful and 2 unfaithful answers (0.909 score).

## Validate the judge

Judge scores are only trusted after comparing them with hand labels on a fixed,
seeded sample of 20 answers (16 attempted answers and 4 refusals; unanswerable
questions are excluded):

```bash
python -m finrag.evaluation.label baseline       # blind: the judge's verdicts are not shown
python -m finrag.evaluation.agreement baseline
```

[`label.py`](label.py) shows each answer next to its reference and saves a
correct / partial / incorrect / refused label after every answer to
`reports/runs/<run>/human_labels.jsonl`. [`agreement.py`](agreement.py) reports
pass/fail agreement (pass = correct), Cohen's kappa, a human-vs-judge table, and
every disagreement with both reasons. The target is at least 80% agreement and
kappa of at least 0.6.

On the baseline, the judge reached 90% agreement and kappa 0.74. Both
disagreements were the judge being more lenient than the human label: it
accepted a right conclusion with wrong reasoning, and missed an answer drawn
from the wrong fiscal year. The judge also never uses the `refused` verdict
(refusals are scored `incorrect`, with the same score of 0).

## Compare runs

```bash
python -m finrag.evaluation.diff dev_baseline my_exp [max_drop]
```

[`diff.py`](diff.py) compares two scored runs on the questions both answered,
so a dev run can be compared with the full baseline. It prints each metric's
change, marked better or worse, and lists questions whose judged correctness
went down or up. It exits with code 1 if correctness drops by more than
`max_drop` (default 0.05), so it can gate CI.

Two independent runs of the unchanged baseline on the dev subset differed in a
single answer (one dropped citation). On the dev subset one question is worth
about 0.05, so treat changes of that size as noise and look for 0.10 or more.

## How it works

The builder caches the two FinanceBench source files, filters their questions
to the configured tickers, fiscal years, and 10-K document type, then maps each
evidence passage to the parsed Item with the greatest three-word-shingle
overlap. It prints evidence mappings below its minimum-match threshold, merges
custom cases, and writes a sorted JSONL golden set. The lookup CLI performs a
case-insensitive substring search across parsed section lines. The deterministic
scorers compare saved outputs with golden evidence and references. The judge
uses versioned prompts and parses a JSON verdict from Groq.

## Limitations

- Evidence-to-Item mapping is lexical and approximate; low-match results are
  reported for human review but are not automatically corrected.
- Building the FinanceBench portion requires network access on the first run
  and assumes its current public file schema.
- Numeric matching and citation checks are heuristics, not semantic answer
  validation.
- The LLM judge can return an invalid response and does not replace human
  review; run faithfulness evaluation before rebuilding the index because it
  uses the current chunk export.
- Judge validation uses 20 labels from one person on one run; agreement may
  differ on later runs whose answers fail in new ways.
- `diff` gates only on judged correctness; retrieval-only changes are shown but
  do not fail the check.