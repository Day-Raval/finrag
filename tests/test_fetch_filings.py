from finrag.ingestion.fetch_filings import find_10ks, fiscal_year


def page(*filings):
    keys = ["form", "accessionNumber", "filingDate", "reportDate", "primaryDocument"]
    return {k: [f[i] for f in filings] for i, k in enumerate(keys)}


class FakeEdgar:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def get(self, url):
        self.calls.append(url)
        data = self.responses[url]
        return type("Resp", (), {"json": lambda self: data})()


def test_fiscal_year_handles_52_53_week_years():
    assert fiscal_year("2022-01-02") == 2021  # J&J FY2021
    assert fiscal_year("2021-12-25") == 2021  # AMD, late December
    assert fiscal_year("2022-05-29") == 2022  # General Mills FY2022
    assert fiscal_year("2022-12-31") == 2022


def test_find_10ks_skips_amendments_and_reads_older_pages_only_when_needed():
    recent = page(
        ("10-K/A", "a-1", "2023-03-01", "2022-12-31", "amend.htm"),
        ("10-K", "a-2", "2023-02-01", "2022-12-31", "fy22.htm"),
        ("4", "a-3", "2022-06-01", "", "form4.xml"),
    )
    older = page(("10-K", "a-4", "2022-02-01", "2021-12-31", "fy21.htm"))
    sub = {
        "name": "ACME",
        "filings": {
            "recent": recent,
            "files": [{"name": "CIK0000000001-submissions-001.json"}],
        },
    }
    edgar = FakeEdgar(
        {
            "https://data.sec.gov/submissions/CIK0000000001.json": sub,
            "https://data.sec.gov/submissions/CIK0000000001-submissions-001.json": older,
        }
    )

    name, found = find_10ks(edgar, 1, {2021, 2022})
    assert name == "ACME"
    assert found[2022]["primary_doc"] == "fy22.htm"
    assert found[2021]["primary_doc"] == "fy21.htm"

    edgar.calls.clear()
    find_10ks(edgar, 1, {2022})
    # FY2022 is on the first page, so no extra page is fetched
    assert len(edgar.calls) == 1
