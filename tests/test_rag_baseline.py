import re

from finrag.corpus.fixed_chunks import fixed_token_chunks
from finrag.generation.answer import format_context


class WhitespaceTokenizer:
    """Stand-in for the HF tokenizer: one token per whitespace-separated word."""

    def __call__(self, text, **kwargs):
        return {"offset_mapping": [m.span() for m in re.finditer(r"\S+", text)]}


def test_chunks_overlap_and_cover_the_whole_text():
    text = " ".join(f"w{i}" for i in range(10))
    chunks = fixed_token_chunks(text, WhitespaceTokenizer(), size=4, overlap=1)
    assert chunks == ["w0 w1 w2 w3", "w3 w4 w5 w6", "w6 w7 w8 w9"]


def test_short_and_empty_text():
    tok = WhitespaceTokenizer()
    assert fixed_token_chunks("only two", tok, size=4, overlap=1) == ["only two"]
    assert fixed_token_chunks("   ", tok, size=4, overlap=1) == []


def test_context_has_citation_headers():
    chunk = {
        "company": "COCA COLA CO",
        "fiscal_year": 2022,
        "item": "8",
        "text": "| Total Assets | $92,763 |",
    }
    assert (
        format_context([chunk])
        == "[1] COCA COLA CO | FY2022 | Item 8\n| Total Assets | $92,763 |"
    )