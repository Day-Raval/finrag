# Failure case study: "Not found" when the evidence was in the context

Two failures caught in Annualyst's own interface during step 1.20, each diagnosed
from the trace. The first is a generation failure that looked like a retrieval
failure; the second is a bug in the tool built to catch answer errors.

## The 60-second version

> I asked my system how Johnson & Johnson's operating income changed from 2021 to
> 2022, and it said "Not found in the filings." My first guess was a retrieval
> miss, but the trace said otherwise: the fourth excerpt was J&J's income-tax note,
> with earnings before taxes for both years, and another excerpt had net earnings.
> J&J simply doesn't report a line called "operating income". When I asked with
> J&J's own term, the same table was retrieved and the answer was right: down from
> $22,776 million to $21,725 million, with every figure tied back to the filing.
> Same evidence, different wording, opposite outcome. So the model read the
> question too literally: refusing was safe, but it should have said the measure
> isn't reported and given the closest one. I fixed the app's question template the
> same day, and queued a one-line prompt rule as an experiment, because my earlier
> prompt changes had made answers less faithful, so it has to earn its place on
> the eval first.

## Case 1: Johnson & Johnson "operating income"

**Symptom.** "How did Johnson & Johnson's operating income change from FY2021 to
FY2022?" returned *Not found in the filings.* The scope was right (JNJ, fiscal 2021
and 2022).
Evidence: [`failure_jnj_before.png`](failure_jnj_before.png),
trace [`failure_jnj_before.json`](failure_jnj_before.json).

**Diagnosis.** The trace shows retrieval did its job. Of the five excerpts:
- excerpt 4 (`JNJ_2022:8:0037`, Note 8 Income Taxes) reports *Earnings before
  taxes on income* of $21,725 million (2022) and $22,776 million (2021);
- excerpt 1 (`JNJ_2022:8:0003`) reports *Net earnings* of $17,941 million and
  $20,878 million.

The model had comparable measures in front of it and still refused.

**Root cause.** J&J has no line called "operating income". The answer prompt says
to answer only from the context and to reply "Not found in the filings" otherwise,
so the model treated "the named measure is absent" as "the answer is absent". The
question came from the app's own coverage rail, whose template assumed every
company reports operating income.

**Confirmation.** Asked with J&J's term, "How did Johnson & Johnson's earnings
before provision for taxes on income change from FY2021 to FY2022?", the same
pipeline retrieved the same income-tax note and answered: fell from $22,776 million
to $21,725 million, a decline of $1,051 million (about $1.1 billion). Tie-out: all
4 figures check out, 2 found in the excerpts and 2 calculated from them
(22,776 − 21,725).
Evidence: [`failure_jnj_after.png`](failure_jnj_after.png),
trace [`failure_jnj_after.json`](failure_jnj_after.json).

**Fixes.**
- Done: the coverage rail now suggests *net income*, which every 10-K reports.
- Queued, as an experiment: one prompt rule, "if the filing does not report the
  measure under that name, say so and give the closest reported measure, named as
  the filing names it". It ships only if a dev run shows no loss in correctness or
  faithfulness; prompts v2 and v3 both made answers less faithful (see the
  [ablation table](../reports/ablation.md)).
- Lower priority: financial synonym expansion at search time. Here retrieval
  already found the table, so it would not have changed the outcome.

**Lessons.**
- Read the trace before blaming a component: "Not found" looked like a retrieval
  miss and was a generation failure.
- Refusing is the right failure mode, safer than inventing a figure, but a useful
  analyst says what *is* reported.

## Case 2: the answer checker was wrong, twice

The app marks every figure in an answer as found in the excerpts, calculated from
them, or not traceable. Real answers broke it in both directions.

1. **Too strict.** A correct Verizon answer ("net income fell from $22.6 billion
   to $21.7 billion, down $0.9 billion, about $870 million") showed 0 of 4 figures
   traceable. The filing reports $22,618 and $21,748 million: the model had rounded
   to billions and subtracted. Fix: rounded billions tie to the figures they round
   from, and a figure that is the difference, sum or % change of figures the
   answer cited is marked *calculated*, with its working shown (22,618 − 21,748).
2. **Then too loose.** "0.9 billion" then showed as *found*, because one-decimal
   rounding allows anything from 850 to 950 million, and an unrelated figure in
   that range sat in another excerpt. Fix: rounded figures must have at least three
   significant digits to tie; vaguer ones must be proven by calculation.

Both cases are pinned as unit tests in [`tests/tieout.test.js`](../tests/tieout.test.js),
which CI runs on every push.

**Lesson.** A guardrail needs its own tests against real outputs. It can fail in
both directions, and each fix can cause the opposite failure.

## Also caught earlier: the citation scorer (step 1.17)

The scorer counted `[Coca-Cola, 2022, Item 8]` as a citation but not
`[KO, FY2022, Item 8]`, because "FY2022" has no word break before the year. Every
run's citation rate was understated (the baseline was 0.333, not 0.290). Found while
writing a test for a new prompt; fixed, all saved runs rescored, and CI now fails
if saved runs and the scorer disagree.