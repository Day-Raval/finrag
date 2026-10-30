from pathlib import Path

from finrag.evaluation.judge import fill, parse


def test_parse_accepts_json_inside_extra_text():
    text = 'Here is my grade:\n{"verdict": "partial", "reason": "one of two figures"}'
    assert parse(text, "correctness") == {
        "verdict": "partial",
        "reason": "one of two figures",
    }


def test_parse_rejects_missing_or_unknown_verdicts():
    assert parse("", "correctness")["verdict"] == "error"
    assert parse(None, "correctness")["verdict"] == "error"  # model returned no content
    assert parse('{"verdict": "great"}', "correctness")["verdict"] == "error"
    assert parse('{"verdict": "correct"}', "faithfulness")["verdict"] == "error"


def test_rubrics_fill_without_breaking_their_json_example():
    for name in ("judge_correctness_v1.md", "judge_faithfulness_v1.md"):
        prompt = fill(
            Path("prompts", name).read_text(),
            question="Q?",
            reference="R.",
            answer="A.",
            context="C.",
        )
        assert "{question}" not in prompt and "QUESTION: Q?" in prompt
        assert '"verdict"' in prompt  # JSON example survives