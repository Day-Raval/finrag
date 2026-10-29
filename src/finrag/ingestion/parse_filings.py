"""parse raw 10-K HTML into one JSONL record per Item section.

Run from the repo root: python -m finrag.ingestion.parse_filings

Tables become Markdown so numbers keep their row/column labels. Writes
data/parsed/<TICKER>_<FY>.jsonl and prints a report flagging filings that
need a manual look.
"""

import csv
import json
import re
import warnings as pywarnings
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, NavigableString, XMLParsedAsHTMLWarning

# Some 10-Ks are XHTML with an <?xml?> header; the HTML parser handles them fine.
pywarnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

ITEMS = "1 1A 1B 1C 2 3 4 5 6 7 7A 8 9 9A 9B 9C 10 11 12 13 14 15 16".split()  # noqa: SIM905
CORE = ["1", "1A", "7", "8"]  # sections the golden questions mostly hit
HEADING = re.compile(r"^item\s*(\d{1,2}[a-c]?)\s*[.:\-–—]?\s*(.*)$", re.IGNORECASE)
# page numbers and running headers
NOISE = re.compile(r"\d{1,3}|table of contents|index", re.IGNORECASE)
BLOCK_TAGS = ["p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"]


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def table_lines(table) -> list[str]:
    # 1. Lay cells out on the real column grid (colspan-aware) so values stay
    #    under their year/header even when a row skips a column.
    rows, spans = [], []
    for tr in table.find_all("tr"):
        cols: list[str] = []
        for td in tr.find_all(["td", "th"]):
            text = clean(td.get_text(" "))
            raw_span = str(td.get("colspan", "1"))
            span = int(raw_span) if raw_span.isdigit() and int(raw_span) > 0 else 1
            if span > 1 and text:
                spans.append((len(rows), len(cols), span, text))  # placed in step 3
                text = ""
            cols += [text] + [""] * (span - 1)
        rows.append(cols)
    width = max(map(len, rows), default=0)
    rows = [r + [""] * (width - len(r)) for r in rows]

    # 2. Glue "$" onto the next value and ")" / "%" onto the previous one.
    for r in rows:
        for j in range(width):
            if r[j] in {"$", "($"}:
                k = next((k for k in range(j + 1, width) if r[k]), None)
                if k is not None:
                    r[k], r[j] = r[j] + r[k], ""
            elif r[j] in {")", "%", ")%"}:
                k = next((k for k in range(j - 1, -1, -1) if r[k]), None)
                if k is not None:
                    r[k], r[j] = r[k] + r[j], ""

    # 3. Put each spanning header over the first column in its span that has data.
    used = {j for r in rows for j, c in enumerate(r) if c}
    for i, start, span, text in spans:
        col = next((j for j in range(start, start + span) if j in used), start)
        rows[i][col] = text
        used.add(col)

    # 4. Drop spacer columns and empty rows.
    keep = sorted(used)
    rows = [[r[j] for j in keep] for r in rows]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    if len(rows) == 1 and sum(map(bool, rows[0])) <= 3:
        # layout table, e.g. "| ITEM 7. | MD&A |" used as a heading
        return [" ".join(c for c in rows[0] if c)]
    lines = ["| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in rows]
    lines.insert(1, "|" + " --- |" * len(keep))
    return lines


def html_to_lines(html: bytes) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    for tag in soup.find_all(style=re.compile(r"display:\s*none", re.IGNORECASE)):
        tag.decompose()  # hidden inline-XBRL facts
    for table in reversed(soup.find_all("table")):  # innermost first for nested tables
        table.replace_with(NavigableString("\n" + "\n".join(table_lines(table)) + "\n"))
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_after("\n")
    lines = (clean(line) for line in soup.get_text().split("\n"))
    return [line for line in lines if line and not NOISE.fullmatch(line)]


def split_sections(lines: list[str]) -> tuple[list[dict], list[str]]:
    positions: dict[str, list[int]] = {}
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if m and len(line) < 200 and m.group(1).upper() in ITEMS:
            positions.setdefault(m.group(1).upper(), []).append(i)
    # Walk items from last (16) to first (1): each takes its latest heading that sits
    # before the next item's. Skips table-of-contents entries and stray later lines
    # that merely start with "Item 1." (e.g. cross-references in Part III).
    chosen: dict[str, int] = {}
    limit = len(lines)
    for item in reversed(ITEMS):
        before = [i for i in positions.get(item, []) if i < limit]
        if before:
            chosen[item] = limit = before[-1]
    starts = sorted((i, item) for item, i in chosen.items())

    sections = []
    if starts and starts[0][0] > 0:
        # cover page: registered securities, shares outstanding, filer status
        cover = "\n".join(lines[: starts[0][0]])
        sections.append({"item": "COVER", "title": "Cover page", "text": cover})
    for k, (i, item) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        title = HEADING.match(lines[i]).group(2) or (
            lines[i + 1] if i + 1 < len(lines) else ""
        )
        sections.append(
            {"item": item, "title": title[:150], "text": "\n".join(lines[i + 1 : end])}
        )

    warnings = [f"missing Item {c}" for c in CORE if c not in chosen]
    for s in sections:
        if s["item"] in ("7", "8") and len(s["text"]) < 5000:
            # Some filers (PepsiCo, Corning) put the statements under another Item.
                        # the full statements are the biggest section mentioning "Total assets"
            home = max(
                (o for o in sections if "Total assets" in o["text"]),
                key=lambda o: len(o["text"]),
                default=None,
            )
            if s["item"] == "8" and home:
                warnings.append(f"note: financial statements are under Item {home['item']}")
    return sections, warnings


def main() -> None:
    cfg = yaml.safe_load(Path("config.yaml").read_text())["corpus"]
    out_dir = Path(cfg["parsed_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    flagged = 0
    with open(cfg["manifest"], newline="") as f:
        manifest = list(csv.DictReader(f))
    for row in manifest:
        doc_id = f"{row['ticker']}_{row['fiscal_year']}"
        sections, warnings = split_sections(
            html_to_lines(Path(row["path"]).read_bytes())
        )
        with open(out_dir / f"{doc_id}.jsonl", "w") as f:
            f.writelines(
                json.dumps(
                    {
                        "doc_id": doc_id,
                        "ticker": row["ticker"],
                        "company": row["company"],
                        "fiscal_year": int(row["fiscal_year"]),
                        "item": s["item"],
                        "title": s["title"],
                        "text": s["text"],
                        "n_chars": len(s["text"]),
                        "url": row["url"],
                    }
                )
                + "\n"
                for s in sections
            )
        sizes = {s["item"]: len(s["text"]) for s in sections if s["item"] in CORE}
        problems = [w for w in warnings if not w.startswith("note:")]
        status = "CHECK" if problems else "ok"
        flagged += bool(problems)
        print(f"{status:5} {doc_id:9} {len(sections):2} sections  core chars {sizes}")
        for w in warnings:
            print(f"      - {w}")
    print(
        f"\nDone. {flagged} filing(s) flagged CHECK -> open them and fix before chunking."
    )


if __name__ == "__main__":
    main()
