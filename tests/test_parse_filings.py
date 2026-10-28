from finrag.ingestion.parse_filings import html_to_lines, split_sections

HTML = b"""<html><body>
<div style="display:none"><span>hidden xbrl fact 999</span></div>
<table>
  <tr><td>ITEM 1. BUSINESS</td><td>3</td></tr>
  <tr><td>ITEM 7. MD&amp;A</td><td>25</td></tr>
</table>
<table><tr><td>ITEM 1.</td><td>BUSINESS</td></tr></table>
<div><span>We make </span><span>chips.</span></div>
<p>12</p>
<div>Item 7. Management's Discussion and Analysis</div>
<table>
  <tr><td></td><td>2022</td><td></td><td>2021</td></tr>
  <tr><td>Revenue</td><td>$</td><td>1,234</td><td>(56</td><td>)</td></tr>
</table>
</body></html>"""


def test_parse_sections_and_tables():
    lines = html_to_lines(HTML)
    assert not any("hidden" in line for line in lines)
    assert "12" not in lines  # page number dropped

    sections, warnings = split_sections(lines)
    assert [s["item"] for s in sections] == ["1", "7"]  # table of contents skipped
    assert sections[0]["text"] == "We make chips."
    assert "| Revenue | $1,234 | (56) |" in sections[1]["text"]
    assert "missing Item 1A" in warnings
