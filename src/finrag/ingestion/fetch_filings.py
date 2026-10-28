"""download 10-K filings from SEC EDGAR and write the manifest.

Run from the repo root:  python -m finrag.ingestion.fetch_filings

Fiscal year = calendar year of the period end (reportDate), except period ends
in the first week of January count as the prior year (52/53-week filers like
J&J). General Mills' fiscal 2022 ends in May 2022, so it stays 2022.
"""

import csv
import hashlib
import os
import time
from itertools import chain
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

MIN_INTERVAL = 0.12  # SEC fair-access rule: at most 10 requests per second
RETRY_STATUS = {429, 500, 502, 503, 504}


class Edgar:
    """Polite EDGAR client: declared User-Agent, rate limit, retries with backoff."""

    def __init__(self, user_agent: str):
        if not user_agent or "@" not in user_agent:
            raise SystemExit('Set SEC_USER_AGENT="Your Name you@example.com" in .env')
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        )
        self._last = 0.0

    def get(self, url: str) -> requests.Response:
        for attempt in range(5):
            time.sleep(max(0.0, MIN_INTERVAL - (time.monotonic() - self._last)))
            self._last = time.monotonic()
            resp = self.session.get(url, timeout=60)
            if resp.status_code not in RETRY_STATUS:
                resp.raise_for_status()
                return resp
            time.sleep(2**attempt)
        resp.raise_for_status()
        return resp


def filing_rows(page: dict):
    """EDGAR stores filings as parallel lists; yield one dict per filing."""
    for i, form in enumerate(page["form"]):
        yield {
            "form": form,
            "accession": page["accessionNumber"][i],
            "filing_date": page["filingDate"][i],
            "report_date": page["reportDate"][i],
            "primary_doc": page["primaryDocument"][i],
        }

def fiscal_year(report_date: str) -> int:
    """52/53-week years can end in the first days of January; that belongs to the prior FY."""
    year, month, day = (int(p) for p in report_date.split("-"))
    return year - 1 if month == 1 and day <= 7 else year

def find_10ks(edgar: Edgar, cik: int, years: set[int]) -> tuple[str, dict[int, dict]]:
    sub = edgar.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
    # Older filings live in extra pages; fetched lazily, only if still needed.
    older = (
        edgar.get(f"https://data.sec.gov/submissions/{f['name']}").json()
        for f in sub["filings"]["files"]
    )
    found: dict[int, dict] = {}
    for page in chain([sub["filings"]["recent"]], older):
        for row in filing_rows(page):
            # Exactly "10-K": skips 10-K/A amendments. Newest first, so the first match wins.
            if (
                row["form"] == "10-K"
                and row["report_date"]
                and fiscal_year(row["report_date"]) in years
            ):
                found.setdefault(fiscal_year(row["report_date"]), row)
        if years <= found.keys():
            break
    return sub["name"], found


def main() -> None:
    load_dotenv()
    cfg = yaml.safe_load(Path("config.yaml").read_text())["corpus"]
    years = set(cfg["years"])
    raw_dir = Path(cfg["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    edgar = Edgar(os.getenv("SEC_USER_AGENT", ""))

    tickers = {
        r["ticker"]: r["cik_str"]
        for r in edgar.get("https://www.sec.gov/files/company_tickers.json")
        .json()
        .values()
    }

    manifest, missing = [], []
    for ticker in cfg["tickers"]:
        if ticker not in tickers:
            missing.append(f"{ticker}: ticker not found on EDGAR")
            continue
        cik = tickers[ticker]
        company, found = find_10ks(edgar, cik, years)
        for fy in sorted(years):
            row = found.get(fy)
            if row is None:
                missing.append(f"{ticker} FY{fy}: no 10-K found")
                continue
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{row['accession'].replace('-', '')}/{row['primary_doc']}"
            path = raw_dir / f"{ticker}_{fy}.htm"
            if not path.exists():  # rerunnable: skips files already downloaded
                tmp = path.with_suffix(".part")
                tmp.write_bytes(edgar.get(url).content)
                tmp.rename(path)  # no half-written .htm if the run is interrupted
            data = path.read_bytes()
            manifest.append(
                {
                    "ticker": ticker,
                    "company": company,
                    "cik": cik,
                    "fiscal_year": fy,
                    "accession": row["accession"],
                    "filing_date": row["filing_date"],
                    "report_date": row["report_date"],
                    "url": url,
                    "path": str(path),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
            print(
                f"ok  {ticker} FY{fy}  period end {row['report_date']}  {len(data) / 1e6:.1f} MB"
            )

    with open(cfg["manifest"], "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)

    expected = len(cfg["tickers"]) * len(years)
    print(f"\n{len(manifest)}/{expected} filings -> {cfg['manifest']}")
    for m in missing:
        print("MISSING", m)


if __name__ == "__main__":
    main()
