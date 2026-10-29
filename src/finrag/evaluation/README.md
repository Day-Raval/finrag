# Evaluation

This package creates and maintains the baseline golden set; automated answer
judging is not implemented yet.

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

Golden-set runs are performed by
[`finrag.answering.run_golden`](../answering/run_golden.py).

## How it works

The builder caches the two FinanceBench source files, filters their questions
to the configured tickers, fiscal years, and 10-K document type, then maps each
evidence passage to the parsed Item with the greatest three-word-shingle
overlap. It prints evidence mappings below its minimum-match threshold, merges
custom cases, and writes a sorted JSONL golden set. The lookup CLI performs a
case-insensitive substring search across parsed section lines.

## Limitations

- Evidence-to-Item mapping is lexical and approximate; low-match results are
  reported for human review but are not automatically corrected.
- Building the FinanceBench portion requires network access on the first run
  and assumes its current public file schema.
- This package creates cases and supports manual evidence lookup; it does not
  score answers, validate citations, or implement the configured judge model.
