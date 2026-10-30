"""Step 1.7: deterministic scorers. No LLM calls, so they cost nothing to run."""

import re

REFUSAL = "not found in the filings"
TOLERANCE = 0.01  # numbers count as equal within ±1%
SCALES = (1, 1_000, 0.001)  # "$1,561 million" vs "$1.561 billion"

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
# whole month names, and a 1-2 digit day not followed by more digits ("December 31,")
MONTH_DAY = re.compile(rf"\b(?:{MONTHS})\s+\d{{1,2}}(?![\d]|[.,]\d)", re.IGNORECASE)
FORM_NAME = re.compile(r"\b10-[KQ]\b", re.IGNORECASE)
NUMBER = re.compile(r"(?<![A-Za-z\d.])\d[\d,]*(?:\.\d+)?")
CITATION = re.compile(r"[\[【][^\]】]*\b(?:19|20)\d{2}\b[^\]】]*[\]】]")


def numbers(text: str) -> list[float]:
    """Numbers in a text, minus years, dates and form names ("10-K")."""
    text = FORM_NAME.sub(" ", MONTH_DAY.sub(" ", text))
    found = []
    for m in NUMBER.finditer(text):
        raw = m.group().rstrip(",")
        value = float(raw.replace(",", ""))
        if re.fullmatch(r"(19|20)\d{2}", raw):
            continue  # a year, not a quantity
        found.append(value)
    return found


def same_number(a: float, b: float) -> bool:
    # shortcut: compares absolute values, so "-$1,561M" matches "(1,561)" and "1,561"
    a, b = abs(a), abs(b)
    if a == 0 or b == 0:
        return a == b
    return any(abs(a * s - b) <= TOLERANCE * b for s in SCALES)


def numeric_match(answer: str, reference: str) -> float | None:
    """Share of the reference's numbers that appear in the answer (None if it has none)."""
    wanted = numbers(reference)
    if not wanted:
        return None
    got = numbers(answer)
    return sum(any(same_number(g, w) for g in got) for w in wanted) / len(wanted)


def refused(answer: str) -> bool:
    return REFUSAL in answer.lower()


def has_citation(answer: str) -> bool:
    """A bracketed reference that includes a year, e.g. [Coca-Cola, 2022, Item 8]."""
    return bool(CITATION.search(answer))


def retrieval_scores(evidence: list[dict], retrieved: list[dict]) -> dict | None:
    """Recall and MRR of retrieved chunks against the golden evidence.

    section_recall: share of evidence (doc, Item) pairs found among the chunks.
    doc_recall:     same, matching the filing only (right company and year).
    mrr:            1 / rank of the first chunk from an evidence section.
    """
    if not evidence:
        return None
    sections = {(e["doc_id"], e["item"]) for e in evidence}
    docs = {e["doc_id"] for e in evidence}
    got_sections = {(r["doc_id"], r["item"]) for r in retrieved}
    got_docs = {r["doc_id"] for r in retrieved}
    rank = next(
        (n for n, r in enumerate(retrieved, 1) if (r["doc_id"], r["item"]) in sections),
        None,
    )
    return {
        "section_recall": len(sections & got_sections) / len(sections),
        "doc_recall": len(docs & got_docs) / len(docs),
        "mrr": 1 / rank if rank else 0.0,
    }