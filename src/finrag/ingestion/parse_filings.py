"""parse raw 10-K HTML into one JSONL record per Item section.

Run from the repo root: python -m finrag.ingestion.parse_filings

Tables become Markdown so numbers keep their row/column labels. Writes
data/parsed/<TICKER>_<FY>.jsonl and prints a report flagging filings that
need a manual look.
"""

import csv
import json
import re
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, NavigableString

ITEMS = "1 1A 1B 1C 2 3 4 5 6 7 7A 8 9 9A 9B 9C 10 11 12 13 14 15 16".split()  # noqa: SIM905
CORE = ["1", "1A", "7", "8"]  # sections the golden questions mostly hit
HEADING = re.compile(r"^item\s*(\d{1,2}[a-c]?)\s*[.:\-–—]?\s*(.*)$", re.IGNORECASE)
# page numbers and running headers
NOISE = re.compile(r"\d{1,3}|table of contents|index", re.IGNORECASE)
BLOCK_TAGS = ["p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"]


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def table_lines(table) -> list[str]:
    rows = []
    for tr in table.find_all("tr"):
        merged: list[str] = []
        for cell in (clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])):
            if not cell:
                continue  # filings use empty cells for spacing
            if merged and cell in {")", "%", ")%"}:
                merged[-1] += cell  # "(56" + ")" -> "(56)"
            elif merged and merged[-1] in {"$", "($"}:
                merged[-1] += cell  # "$" + "1,234" -> "$1,234"
            else:
                merged.append(cell)
        if merged:
            rows.append(merged)
    if not rows:
        return []
    if len(rows) == 1 and len(rows[0]) <= 3:
        # layout table, e.g. "| ITEM 7. | MD&A |" used as a heading
        return [" ".join(rows[0])]
    width = max(map(len, rows))
    # shortcut: rows are left-aligned after dropping spacer cells, so a short row
    # can shift columns; fix if numeric QA suffers
    lines = [
        "| "
        + " | ".join(c.replace("|", "/") for c in r + [""] * (width - len(r)))
        + " |"
        for r in rows
    ]
    lines.insert(1, "|" + " --- |" * width)
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
    last: dict[str, int] = {}
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if m and len(line) < 200 and m.group(1).upper() in ITEMS:
            # the table of contents comes first, so the last match is the real heading
            last[m.group(1).upper()] = i
    starts = sorted((i, item) for item, i in last.items())

    sections = []
    for k, (i, item) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        title = HEADING.match(lines[i]).group(2) or (
            lines[i + 1] if i + 1 < len(lines) else ""
        )
        sections.append(
            {"item": item, "title": title[:150], "text": "\n".join(lines[i + 1 : end])}
        )

    warnings = [f"missing Item {c}" for c in CORE if c not in last]
    order = [s["item"] for s in sections]
    if order != sorted(order, key=ITEMS.index):
        warnings.append(f"items out of order: {order}")
    for s in sections:
        if s["item"] in ("7", "8") and len(s["text"]) < 5000:
            warnings.append(
                f"Item {s['item']} only {len(s['text'])} chars (incorporated by reference?)"
            )
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
        status = "CHECK" if warnings else "ok"
        flagged += bool(warnings)
        print(f"{status:5} {doc_id:9} {len(sections):2} sections  core chars {sizes}")
        for w in warnings:
            print(f"      - {w}")
    print(
        f"\nDone. {flagged} filing(s) flagged CHECK -> open them and fix before chunking."
    )


if __name__ == "__main__":
    main()
