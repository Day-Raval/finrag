"""Step 1.5: build evals/golden.jsonl from FinanceBench seeds + hand-written cases.

Run from the repo root:  python -m finrag.evaluation.build_golden

1. Downloads the FinanceBench open sample (cached in data/financebench/).
2. Keeps questions about our tickers and fiscal years (10-Ks only).
3. Maps each evidence passage to the parsed Item section it came from.
4. Appends the hand-written cases in evals/custom.jsonl.
"""

import json
import re
from pathlib import Path

import requests
import yaml

FB_URL = "https://raw.githubusercontent.com/patronus-ai/financebench/main/data/"
FB_FILES = ["financebench_open_source.jsonl", "financebench_document_information.jsonl"]

# FinanceBench company names -> our tickers
TICKERS = {
    "AMD": "AMD", "Boeing": "BA", "American Express": "AXP", "PepsiCo": "PEP",
    "3M": "MMM", "Verizon": "VZ", "CVS Health": "CVS", "AES Corporation": "AES",
    "Johnson & Johnson": "JNJ", "Corning": "GLW", "Lockheed Martin": "LMT",
    "Coca-Cola": "KO", "American Water Works": "AWK", "General Mills": "GIS",
    "Pfizer": "PFE",
}  # fmt: skip
CATEGORIES = {"extraction", "numeric", "reasoning", "open", "comparison", "multi_year", "unanswerable"}  # fmt: skip
MIN_MATCH = 0.5  # below this, the evidence-to-section mapping needs a manual look


def category(reasoning: str | None) -> str:
    """Collapse FinanceBench's reasoning labels into our categories."""
    r = (reasoning or "").lower()
    if "logical" in r:
        return "reasoning"
    if "numerical" in r:
        return "numeric"
    if "extraction" in r:
        return "extraction"
    return "open"  # FinanceBench "novel-generated" questions carry no label


def tokens(text: str) -> list[str]:
    # words and numbers only, so PDF text ("$\n34,229") matches Markdown ("$34,229")
    return re.findall(r"[a-z]+|\d+(?:[.,]\d+)*", text.lower())


def shingles(toks: list[str], n: int = 3) -> set[tuple[str, ...]]:
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def best_section(evidence: str, sections: dict[str, set]) -> tuple[str | None, float]:
    """Item whose text shares the most 3-word sequences with the evidence."""
    ev = shingles(tokens(evidence))
    if not ev or not sections:
        return None, 0.0
    item, overlap = max(
        ((k, len(ev & s)) for k, s in sections.items()), key=lambda x: x[1]
    )
    return item, round(overlap / len(ev), 3)


def load_financebench(cache: Path) -> tuple[list[dict], dict[str, dict]]:
    cache.mkdir(parents=True, exist_ok=True)
    for name in FB_FILES:
        path = cache / name
        if not path.exists():
            resp = requests.get(FB_URL + name, timeout=60)
            resp.raise_for_status()
            path.write_bytes(resp.content)
    questions = [json.loads(line) for line in (cache / FB_FILES[0]).open()]
    docs = {d["doc_name"]: d for d in map(json.loads, (cache / FB_FILES[1]).open())}
    return questions, docs


def main() -> None:
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    corpus, golden_cfg = cfg["corpus"], cfg["golden"]
    questions, docs = load_financebench(Path(golden_cfg["financebench_dir"]))

    def doc_id(doc_name: str) -> str | None:
        d = docs[doc_name]
        ticker = TICKERS.get(d["company"])
        ok = (
            ticker in corpus["tickers"]
            and d["doc_period"] in corpus["years"]
            and d["doc_type"].lower() == "10k"
        )
        return f"{ticker}_{d['doc_period']}" if ok else None

    section_cache: dict[str, dict[str, set]] = {}

    def sections(did: str) -> dict[str, set]:
        if did not in section_cache:
            path = Path(corpus["parsed_dir"]) / f"{did}.jsonl"
            section_cache[did] = {
                r["item"]: shingles(tokens(r["text"]))
                for r in map(json.loads, path.open())
            }
        return section_cache[did]

    golden, weak = [], []
    for q in questions:
        did = doc_id(q["doc_name"])
        if did is None:
            continue
        evidence = []
        for ev in q["evidence"]:
            ev_did = doc_id(ev["doc_name"]) or did
            item, score = best_section(ev["evidence_text"], sections(ev_did))
            evidence.append({"doc_id": ev_did, "item": item, "match": score})
            if score < MIN_MATCH:
                weak.append(
                    f"{q['financebench_id']} {ev_did} Item {item} match={score}"
                )
        ticker, year = did.split("_")
        golden.append({
            "id": q["financebench_id"].replace("financebench_id_", "fb_"),
            "source": "financebench",
            "question": q["question"],
            "answer": q["answer"],
            "category": category(q["question_reasoning"]),
            "ticker": ticker,
            "fiscal_year": int(year),
            "evidence": evidence,
            "justification": q.get("justification") or "",
        })  # fmt: skip

    seeds = len(golden)
    custom = Path(golden_cfg["custom"])
    if custom.exists():
        golden += [json.loads(line) for line in custom.open() if line.strip()]

    out = Path(golden_cfg["path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        f.writelines(
            json.dumps(g) + "\n" for g in sorted(golden, key=lambda g: g["id"])
        )

    counts: dict[str, int] = {}
    for g in golden:
        counts[g["category"]] = counts.get(g["category"], 0) + 1
    print(
        f"{len(golden)} cases ({seeds} FinanceBench + {len(golden) - seeds} custom) -> {out}"
    )
    print("by category:", dict(sorted(counts.items())))
    for w in weak:
        print("LOW MATCH", w)


if __name__ == "__main__":
    main()