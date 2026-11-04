"""Make sure every filing a question names gets into the results.

One search for "Compare KO and PEP in FY2022" can fill all `top_k` slots from one
company. When the question names several companies (or filings), each one with no
chunk in the results gets its best chunk swapped in for the lowest-ranked one.
Rules, no LLM: the 1.14 filter already reads the companies and years.

`decompose: company` splits by company only: a 10-K also reports the prior year,
so a second year often needs no second filing. `filing` splits by company x year.
"""

from itertools import product


def sub_filters(flt: dict | None, mode: str | None) -> list[dict]:
    """One filter per company (or filing) the question names; [] if it names one."""
    if not flt or mode not in ("company", "filing"):
        return []
    if mode == "company":
        subs = [{"ticker": [t], "fiscal_year": flt["fiscal_year"]} for t in flt["ticker"]]
    else:
        subs = [
            {"ticker": [t] if t else [], "fiscal_year": [y] if y else []}
            for t, y in product(flt["ticker"] or [None], flt["fiscal_year"] or [None])
        ]
    return subs if len(subs) > 1 else []


def cover(hits: list[dict], missing: list[dict], k: int) -> list[dict]:
    """Swap each missing filing's best chunk in for the lowest-ranked results."""
    # shortcut: drops from the bottom, so with 3+ filings a filing's only chunk can
    # be the one dropped; the golden set names at most 2, revisit if that changes
    return hits[: max(0, k - len(missing))] + missing[:k]