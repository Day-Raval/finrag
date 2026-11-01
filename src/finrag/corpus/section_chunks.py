"""structure-aware chunking of parsed 10-K sections.

A section is split into blocks: one block per paragraph line, and one per
Markdown table (its rows plus the short line just above it, which is usually the
table's title). Blocks are packed in order into chunks of at most `size` tokens,
so a paragraph or table row is never cut in half. A table longer than `size` is
split by rows, and every piece repeats the title and header rows so its numbers
keep their labels. A paragraph longer than `size` falls back to fixed windows.
"""

from finrag.corpus.fixed_chunks import fixed_token_chunks

CAPTION_MAX_CHARS = 200  # a longer line above a table is a paragraph, not a title


def blocks(text: str) -> list[tuple[list[str], list[str]]]:
    """(head, body) per block. Paragraph: head=[]. Table: head=title + header rows."""
    lines = [line for line in text.split("\n") if line.strip()]
    out: list[tuple[list[str], list[str]]] = []
    i = 0
    while i < len(lines):
        if not lines[i].startswith("|"):
            out.append(([], [lines[i]]))
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].startswith("|"):
            j += 1
        table = lines[i:j]
        caption = []
        if out and not out[-1][0] and len(out[-1][1][0]) < CAPTION_MAX_CHARS:
            caption = out.pop()[1]
        # parse_filings always writes the header row then the "| --- |" separator
        out.append((caption + table[:2], table[2:]))
        i = j
    return out


def section_token_chunks(text: str, tokenizer, size: int) -> list[str]:
    def n_tokens(s: str) -> int:
        return len(tokenizer(s, add_special_tokens=False, verbose=False)["input_ids"])

    # shortcut: chunk size = sum of per-line token counts, which can be a few
    # tokens off the joined text; the embedder truncates at 512 anyway
    pieces: list[tuple[str, int]] = []  # each piece fits in `size`
    for head, body in blocks(text):
        if not head:
            line = body[0]
            n = n_tokens(line)
            if n <= size:
                pieces.append((line, n))
            else:
                pieces += [
                    (p, size) for p in fixed_token_chunks(line, tokenizer, size, 0)
                ]
            continue
        head_n = sum(map(n_tokens, head))
        rows, rows_n = [], head_n
        for row in body:
            n = n_tokens(row)
            if rows and rows_n + n > size:
                pieces.append(("\n".join(head + rows), rows_n))
                rows, rows_n = [], head_n
            rows.append(row)
            rows_n += n
        pieces.append(("\n".join(head + rows), rows_n))

    chunks, current, current_n = [], [], 0
    for piece, n in pieces:
        if current and current_n + n > size:
            chunks.append("\n".join(current))
            current, current_n = [], 0
        current.append(piece)
        current_n += n
    if current:
        chunks.append("\n".join(current))
    return chunks