import re

from finrag.corpus.section_chunks import blocks, section_token_chunks
from finrag.indexing.build_index import embed_text


class WordTokenizer:
    """Stand-in for the HF tokenizer: one token per whitespace-separated word."""

    def __call__(self, text, **kwargs):
        spans = [m.span() for m in re.finditer(r"\S+", text)]
        return {"input_ids": list(range(len(spans))), "offset_mapping": spans}


TABLE = [
    "| | 2022 | 2021 |",
    "| --- | --- | --- |",
    "| Revenue | $10 | $9 |",
    "| Total assets | $50 | $40 |",
]


def test_table_keeps_its_title_as_one_block():
    text = "Intro paragraph here.\nConsolidated Balance Sheet\n" + "\n".join(TABLE)
    assert blocks(text) == [
        ([], ["Intro paragraph here."]),
        (["Consolidated Balance Sheet", *TABLE[:2]], TABLE[2:]),
    ]


def test_blocks_pack_without_splitting_lines():
    text = "one two three\nfour five six\nseven eight nine"
    assert section_token_chunks(text, WordTokenizer(), size=6) == [
        "one two three\nfour five six",
        "seven eight nine",
    ]


def test_long_table_repeats_title_and_header_rows():
    rows = [f"| Line {i} | ${i} | ${i} |" for i in range(6)]
    text = "Income Statement\n" + "\n".join(TABLE[:2] + rows)
    chunks = section_token_chunks(text, WordTokenizer(), size=40)
    assert len(chunks) > 1
    for c in chunks:
        assert c.startswith("Income Statement\n| | 2022 | 2021 |\n| --- |")
    assert sum(c.count("| Line") for c in chunks) == 6  # every row kept once


def test_long_paragraph_falls_back_to_fixed_windows():
    text = " ".join(f"w{i}" for i in range(10))
    assert section_token_chunks(text, WordTokenizer(), size=4) == [
        "w0 w1 w2 w3",
        "w4 w5 w6 w7",
        "w8 w9",
    ]


def test_embed_text_header():
    chunk = {
        "company": "KO",
        "fiscal_year": 2022,
        "item": "8",
        "title": "FS",
        "text": "x",
    }
    assert embed_text(chunk, header=False) == "x"
    assert embed_text(chunk, header=True) == "KO | FY2022 | Item 8: FS\nx"