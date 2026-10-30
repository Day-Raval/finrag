import json
from pathlib import Path

import pytest

from finrag.evaluation.scorers import (
    has_citation,
    numbers,
    numeric_match,
    refused,
    retrieval_scores,
)

GOLDEN = Path("evals/golden.jsonl")


def test_numbers_skip_years_dates_and_form_names():
    text = "Approximately 142,000 as of December 31, 2021 (FY2021 10-K); margin 0.62%"
    assert numbers(text) == [142000.0, 0.62]
    # "margin" and "May" must not be read as dates
    assert numbers("gross margin 45% in May 2022") == [45.0]


def test_numeric_match_tolerance_scale_and_sign():
    assert numeric_match("ratio of 2.77", "approximately 2.774729") == 1.0  # within 1%
    assert numeric_match("$1.561 billion", "-$1561M") == 1.0  # scale + sign
    assert (
        numeric_match("$86,392M and $40,000M", "$86,392 million vs $43,004 million")
        == 0.5
    )
    assert numeric_match("Yes", "Yes, change in PPNE was positive") is None


def test_refusal_and_citation():
    assert refused("Not found in the filings.")
    assert not refused("Revenue was $5 billion.")
    assert has_citation(
        "Total assets were $92,763 million [COCA COLA CO, 2022, Item 8]."
    )
    assert has_citation("$92,763 million【3, 2022, Balance Sheet】")
    assert not has_citation("Total assets were $92,763 million.")


def test_retrieval_scores():
    evidence = [{"doc_id": "KO_2022", "item": "8"}, {"doc_id": "PEP_2022", "item": "7"}]
    retrieved = [
        {"doc_id": "KO_2021", "item": "8"},  # wrong year
        {"doc_id": "KO_2022", "item": "8"},
        {"doc_id": "PEP_2022", "item": "1"},  # right filing, wrong section
    ]
    assert retrieval_scores(evidence, retrieved) == {
        "section_recall": 0.5,
        "doc_recall": 1.0,
        "mrr": 0.5,
    }
    assert retrieval_scores([], retrieved) is None


@pytest.mark.skipif(not GOLDEN.exists(), reason="no golden set")
def test_every_reference_answer_matches_itself():
    """Sanity check: scoring a reference against itself must be perfect."""
    for g in map(json.loads, GOLDEN.open()):
        assert numeric_match(g["answer"], g["answer"]) in (None, 1.0), g["id"]
        assert refused(g["answer"]) == (g["category"] == "unanswerable"), g["id"]