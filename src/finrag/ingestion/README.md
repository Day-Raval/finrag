# Ingestion

Downloads SEC 10-K filings from EDGAR and turns them into clean, section-level
records that downstream stages (chunking, indexing) can trace back to a company,
fiscal year, and 10-K Item.

| Module | Step | Input | Output |
| --- | --- | --- | --- |
| `fetch_filings.py` | 1.3 | `config.yaml` (tickers, years) | `data/raw/<TICKER>_<FY>.htm`, `data/manifest.csv` |
| `parse_filings.py` | 1.4 | `data/manifest.csv`, raw HTML | `data/parsed/<TICKER>_<FY>.jsonl` |

Chunking is not implemented yet; it arrives with the baseline RAG (step 1.6).

## Run

From the repo root, with `SEC_USER_AGENT` set in `.env`:

```bash
python -m finrag.ingestion.fetch_filings   # ~2-5 min, rerunnable (skips existing files)
python -m finrag.ingestion.parse_filings   # prints a per-filing ok/CHECK report
```

`data/` is gitignored. Rebuild it from these two commands; `manifest.csv`
records a SHA-256 per filing so a rebuild can be checked against a previous run.

## Fetching (`fetch_filings.py`)

- Resolves tickers to CIKs via `company_tickers.json`, then reads each company's
  EDGAR submissions feed. Older filing pages are fetched only if still needed.
- Keeps exactly `10-K` forms; `10-K/A` amendments are skipped.
- **Fiscal year** = year of the period end, except period ends in the first week
  of January count as the prior year. This handles 52/53-week filers such as
  Johnson & Johnson (FY2021 ends 2022-01-02). Non-calendar filers keep their own
  label (General Mills FY2022 ends 2022-05-29).
- Follows SEC fair-access rules: declared User-Agent, at most 10 requests/second,
  exponential backoff on 429/5xx.
- Writes each file via a `.part` temp file, so an interrupted run never leaves a
  half-written filing.

### `manifest.csv` columns

`ticker, company, cik, fiscal_year, accession, filing_date, report_date, url, path, bytes, sha256`

## Parsing (`parse_filings.py`)

- Removes scripts, styles, and hidden inline-XBRL facts (`display:none`).
- Converts tables to Markdown on the real column grid (colspan-aware), so each
  value stays under its year header even when a row skips a cell. `$` is joined
  to the following value; `)` and `%` to the preceding one. Spacer columns and
  empty rows are dropped.
- Treats one-row layout tables as text, since some filers (e.g. Pfizer) build
  section headings as `| ITEM 1. | BUSINESS |`.
- Drops page numbers and running headers ("Table of contents", "Index").
- **Section splitting:** matches `Item N.` heading lines, then walks Items from
  16 back to 1, giving each the latest heading that sits before the next Item's.
  This skips table-of-contents entries and stray lines that merely start with
  "Item 1." (a real case in General Mills FY2022).

### Output record (one JSON line per Item)

```json
{
  "doc_id": "KO_2022",
  "ticker": "KO",
  "company": "COCA COLA CO",
  "fiscal_year": 2022,
  "item": "8",
  "title": "FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA",
  "text": "...Markdown tables and paragraphs...",
  "n_chars": 259996,
  "url": "https://www.sec.gov/Archives/edgar/data/..."
}
```

### Report

Each filing prints `ok` or `CHECK`. `CHECK` means a core Item (1, 1A, 7, 8) is
missing, or Item 7/8 is under 5,000 characters. When Item 8 is only a pointer,
the report notes where the statements actually are instead of flagging the
filing.

## Known filing quirks

| Filing | Quirk | Effect |
| --- | --- | --- |
| PepsiCo (PEP) | Item 8 says "See Item 15"; statements are inside Item 7 | PEP Item 7 is ~2x typical size |
| Corning (GLW) | Statements follow the Item 16 heading at the end of the filing | Statements are labelled Item 16 |
| Johnson & Johnson (JNJ) | 52/53-week fiscal year ending in early January | Handled by the fiscal-year rule |
| General Mills FY2022 (GIS_2022) | Tables use positioned text boxes, not `<table>`: 0 Markdown rows, one cell per line, and lone 1–3 digit cells are dropped as page numbers | Numeric questions on GIS_2022 are harder; candidate fix in step 1.11 |

Retrieval searches text regardless of Item label, so these do not lose content,
but the `item` field does not always describe what the section contains.

## Limitations

- A spanning header is placed over the first column in its span that holds
  data; unusual header layouts may still land one column off.
- Exhibits (e.g. EX-13 annual reports) are not downloaded; all 30 current filings
  carry their statements in the main 10-K document.
- Heading detection assumes lines start with `Item N`. A new filer with a
  different style will show up as `CHECK` in the report.

## Tests

```bash
pytest tests/test_fetch_filings.py tests/test_parse_filings.py
```

Offline, with no SEC calls. They cover amendments, lazy paging, 52/53-week fiscal
years, table-of-contents skipping, stray Item lines, column alignment, and
statements that sit under a different Item.