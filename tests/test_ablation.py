import json

from finrag.evaluation.ablation import build, judge_score


def test_judge_score_uses_the_last_verdict_and_skips_unanswerable(tmp_path):
    path = tmp_path / "judge_correctness.jsonl"
    rows = [
        {"id": "a", "category": "numeric", "verdict": "error"},
        {"id": "a", "category": "numeric", "verdict": "correct"},  # retry wins
        {"id": "b", "category": "numeric", "verdict": "partial"},
        {"id": "c", "category": "unanswerable", "verdict": "correct"},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert judge_score(path, "correctness") == 0.75
    assert judge_score(tmp_path / "missing.jsonl", "correctness") is None


def test_build_fills_saved_numbers_and_dashes_for_missing(tmp_path):
    (tmp_path / "retrieval").mkdir()
    (tmp_path / "retrieval" / "fixed_512_64_hdr.json").write_text(
        json.dumps({"overall": {"section_recall": 0.652, "doc_recall": 0.971, "mrr": 0.408}})
    )
    run = tmp_path / "runs" / "dev_retrieval"
    run.mkdir(parents=True)
    (run / "summary.json").write_text(json.dumps(
        {"false_refusal_rate": 0.381, "p95_s": 28.05, "tokens_per_question": 3098, "overall": {"citation": 0.714}}
    ))  # fmt: skip
    table = build(tmp_path)
    assert "| `fixed_512_64_hdr` | 0.652 | 0.971 | 0.408 | — | — |" in table
    assert "| `dev_retrieval` | — | — | 0.381 | 0.714 | 28.1 | 3,098 | 3.1M |" in table
    assert "`dense_fixed_512_64` | — | — | — |" in table  # report not present