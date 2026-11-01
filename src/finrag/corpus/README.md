# Corpus

This package turns parsed 10-K sections into chunks for indexing. Two
strategies are available, selected by `chunking.strategy` in the config:

| Strategy | Module | What it does |
| --- | --- | --- |
| `fixed` (baseline) | [`fixed_chunks.py`](fixed_chunks.py) | Token windows of `size` tokens that overlap by `overlap` tokens |
| `section` (step 1.11) | [`section_chunks.py`](section_chunks.py) | Packs whole paragraphs and table rows into chunks of at most `size` tokens |

`iter_chunks(parsed_dir, split)` reads `data/parsed/*.jsonl`, applies the chosen
strategy to each section, and yields one record per chunk. Each record keeps
`chunk_id`, document, company, fiscal year, Item, title, source URL, and the
exact source text, so retrieved evidence stays citable.

The index builder invokes this package:

```bash
python -m finrag.indexing.build_index                                          # baseline (fixed)
FINRAG_CONFIG=configs/section_512.yaml python -m finrag.indexing.build_index   # section-aware
```

## How it works

`fixed_token_chunks()` gets character offsets from the Hugging Face tokenizer
and slices the original text with them, so Markdown tables are preserved
exactly. Consecutive windows advance by `size - overlap` tokens.

`section_token_chunks()` first splits a section into blocks: one per paragraph
line, and one per Markdown table, including the short line just above the
table, which is usually its title. It then packs blocks in order into chunks of
at most `size` tokens. A table that does not fit is split by rows, and every
piece repeats the title and header rows so its numbers keep their year labels.
A paragraph longer than `size` falls back to fixed windows.

Chunk IDs are `<doc_id>:<item>:<n>`, stable for a given strategy and size.

## Result

On the 69 answerable golden questions, section-aware chunking did not beat the
baseline: section recall@5 was 0.522 at 512 tokens and 0.551 at 256, against
0.543 for fixed 512/64 windows. With a contextual header it reached 0.551,
below the 0.652 of fixed windows with the same header. A likely cause is that
section chunks have no overlap, so content near a boundary appears in only one
chunk. Fixed 512/64 windows remain the chunking strategy of choice.

## Limitations

- Fixed windows can split a table or sentence between chunks; the overlap
  softens this but does not remove it.
- Section chunk sizes are the sum of per-line token counts, which can differ by
  a few tokens from the joined text; the embedder truncates at 512 tokens.
- Section chunks have no overlap between neighbours.
- Chunking reads every parsed section from disk and the index builder collects
  every chunk before embedding, so it is not streaming.
- Chunk-size and overlap settings are not validated; invalid values in the
  config can cause incorrect stepping or errors.