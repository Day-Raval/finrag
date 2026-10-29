import json
from pathlib import Path

import pytest

from finrag.evaluation.build_golden import (
    CATEGORIES,
    best_section,
    category,
    shingles,
    tokens,
)

GOLDEN = Path("evals/golden.jsonl")


def test_evidence_maps_pdf_text_to_markdown_section():
    sections = {
        "7": shingles(tokens("Revenue grew because of pricing.")),
        "8": shingles(tokens("| Net sales | $34,229 | $35,355 | $32,184 |")),
    }
    item, score = best_section("Net sales\n$\n34,229 $\n35,355 $\n32,184", sections)
    assert item == "8" and score == 1.0


def test_financebench_labels_collapse_to_our_categories():
    assert category("Logical reasoning (based on numerical reasoning)") == "reasoning"
    assert category("Numerical reasoning OR information extraction") == "numeric"
    assert category("Information extraction") == "extraction"
    assert category(None) == "open"


@pytest.mark.skipif(
    not GOLDEN.exists(), reason="run python -m finrag.evaluation.build_golden"
)
def test_golden_set_is_complete():
    rows = [json.loads(line) for line in GOLDEN.open()]
    assert len(rows) >= 60
    assert len({r["id"] for r in rows}) == len(rows), "duplicate ids"
    for r in rows:
        assert {
            "id",
            "source",
            "question",
            "answer",
            "category",
            "evidence",
        } <= r.keys(), r["id"]
        assert r["category"] in CATEGORIES, r["id"]
        assert "TODO" not in json.dumps(r), f"{r['id']} still has a TODO"
        if r["category"] == "unanswerable":
            assert r["answer"] == "Not found in the filings." and r["evidence"] == []
        else:
            assert r["evidence"], f"{r['id']} has no evidence"
    missing = CATEGORIES - {r["category"] for r in rows}
    assert not missing, f"no cases for: {missing}"