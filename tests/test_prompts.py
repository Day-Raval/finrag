from pathlib import Path

from finrag.evaluation.scorers import REFUSAL, has_citation


def test_answer_prompts_fill_and_keep_the_refusal_phrase():
    for path in sorted(Path("prompts").glob("answer_v*.md")):
        text = path.read_text()
        filled = text.format(context="[1] KO | FY2022 | Item 8\nTotal assets $92,763", question="Q?")
        assert "Total assets $92,763" in filled and "Q?" in filled, path  # no stray {braces}
        assert REFUSAL in text.lower(), path  # score_run counts refusals by this phrase


def test_prompt_citation_formats_are_scored_as_citations():
    assert has_citation("Total assets were $92,763 million [Coca-Cola, 2022, Item 8].")
    assert has_citation("Total assets were $92,763 million [Coca-Cola, FY2022, Item 8].")