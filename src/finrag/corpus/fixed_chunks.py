"""Fixed-size token chunking of parsed 10-K sections (baseline strategy)."""

import json
from collections.abc import Iterator
from pathlib import Path


def fixed_token_chunks(text: str, tokenizer, size: int, overlap: int) -> list[str]:
    """Windows of `size` tokens, each starting `size - overlap` tokens after the last.

    Slices the original text by token offsets, so chunks keep the exact source text
    (Markdown tables included) rather than a lossy detokenized version.
    """
    spans = tokenizer(
        text, add_special_tokens=False, return_offsets_mapping=True, verbose=False
    )["offset_mapping"]
    if not spans:
        return []
    step = size - overlap
    return [
        text[spans[i][0] : spans[min(i + size, len(spans)) - 1][1]]
        for i in range(0, max(len(spans) - overlap, 1), step)
    ]


def iter_chunks(parsed_dir: str, tokenizer, size: int, overlap: int) -> Iterator[dict]:
    """One record per chunk, carrying the metadata citations need."""
    for path in sorted(Path(parsed_dir).glob("*.jsonl")):
        for section in map(json.loads, path.open()):
            pieces = fixed_token_chunks(section["text"], tokenizer, size, overlap)
            for n, text in enumerate(pieces):
                yield {
                    "chunk_id": f"{section['doc_id']}:{section['item']}:{n:04d}",
                    "doc_id": section["doc_id"],
                    "ticker": section["ticker"],
                    "company": section["company"],
                    "fiscal_year": section["fiscal_year"],
                    "item": section["item"],
                    "title": section["title"],
                    "url": section["url"],
                    "text": text,
                }