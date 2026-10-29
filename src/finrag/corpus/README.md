# Corpus

This package implements the baseline chunking strategy for parsed 10-K sections.
[`fixed_chunks.py`](fixed_chunks.py) uses the configured embedding model's
tokenizer to create 512-token windows with a 64-token overlap.

`iter_chunks()` reads `data/parsed/*.jsonl` and yields one record per window.
Each record preserves `chunk_id`, document, company, fiscal year, Item, title,
source URL, and exact source text so retrieved evidence remains citable. Text is
sliced by tokenizer offsets rather than detokenized, preserving Markdown tables.

The index builder invokes this package:

```bash
python -m finrag.indexing.build_index
```

## How it works

`fixed_token_chunks()` obtains character offsets from the Hugging Face tokenizer
and uses those offsets to slice the original text. Consecutive windows advance
by `size - overlap` tokens, so the baseline configuration produces 512-token
chunks that repeat 64 tokens at each boundary. `iter_chunks()` applies that
logic to every section in every parsed filing and assigns a stable chunk ID from
the document ID, Item, and chunk number.

## Limitations

- Fixed windows do not respect semantic boundaries; a table or sentence can be
  split between chunks despite the overlap.
- Chunking reads every parsed section from disk and the index builder collects
  every yielded chunk before embedding, so the baseline is not streaming.
- The implementation does not validate chunk-size or overlap settings; invalid
  values in `config.yaml` can cause incorrect stepping or errors.
