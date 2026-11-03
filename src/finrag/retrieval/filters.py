"""Read which companies and fiscal years a question asks about.

Rules, not an LLM, so filtering costs nothing. An empty list means "don't
filter on this field", so a question that names no known company or corpus
year is searched across everything.
"""

import re

# Names analysts use for each company; matched as whole words, case-insensitive.
ALIASES = {
    "AMD": ["amd", "advanced micro devices"],
    "BA": ["boeing"],
    "AXP": ["american express", "amex"],
    "PEP": ["pepsico", "pepsi"],
    "MMM": ["3m"],
    "VZ": ["verizon"],
    "CVS": ["cvs"],
    "AES": ["aes"],
    "JNJ": ["johnson & johnson", "johnson and johnson", "jnj", "j&j"],
    "GLW": ["corning"],
    "LMT": ["lockheed"],
    "KO": ["coca-cola", "coca cola", "coke"],
    "AWK": ["american water"],
    "GIS": ["general mills"],
    "PFE": ["pfizer"],
}
# FY2022, FY 2022, FY22, FY'22, or a bare 20xx ("fiscal 2022", "in 2022")
YEAR = re.compile(r"\bFY\s?'?(\d{4}|\d{2})\b|\b(20\d{2})\b", re.IGNORECASE)


def question_filter(question: str, cfg: dict) -> dict[str, list]:
    q = question.lower()
    tickers = sorted(
        t
        for t, names in ALIASES.items()
        if t in cfg["corpus"]["tickers"]
        and any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", q) for n in names)
    )
    years = {int(fy) if len(fy) == 4 else 2000 + int(fy) for fy, _ in YEAR.findall(question) if fy}
    years |= {int(y) for _, y in YEAR.findall(question) if y}
    # years outside the corpus (FY2023 forecasts, FY2019 comparisons) can't be filtered on
    return {"ticker": tickers, "fiscal_year": sorted(years & set(cfg["corpus"]["years"]))}


def matches(chunk: dict, flt: dict | None) -> bool:
    return not flt or all(not v or chunk[k] in v for k, v in flt.items())