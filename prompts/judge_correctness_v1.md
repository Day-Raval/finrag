You are grading an answer to a question about a company's SEC 10-K filing.
Compare the ANSWER with the REFERENCE answer.

Verdicts:
- "correct": same conclusion and the same key figures as the reference. Rounding and different units are fine if the values agree within about 1% (e.g. $1.58 billion vs $1,577 million).
- "partial": part of it is right (e.g. one of two figures, or the right figure with a wrong conclusion).
- "incorrect": wrong figures, wrong conclusion, or the wrong company or year.
- "refused": the answer says the information was not found, or does not attempt an answer.
If the REFERENCE is "Not found in the filings.", a refusal is "correct" and any attempted answer is "incorrect".
Ignore citation format and writing style.

Return only JSON: {"verdict": "correct" | "partial" | "incorrect" | "refused", "reason": "<one sentence>"}

QUESTION: {question}
REFERENCE: {reference}
ANSWER: {answer}