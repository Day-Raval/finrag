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
  <tr><td></td><td colspan="3">2022</td><td colspan="3">2021</td></tr>
  <tr><td>Revenue</td><td>$</td><td>1,234</td><td></td><td>$</td><td>(56</td><td>)</td></tr>
</table>
</body></html>"""


def test_parse_sections_and_tables():
    lines = html_to_lines(HTML)
    assert not any("hidden" in line for line in lines)
    assert "12" not in lines  # page number dropped

    sections, warnings = split_sections(lines)
    # cover page (here: the table of contents) is kept; TOC entries aren't headings
    assert [s["item"] for s in sections] == ["COVER", "1", "7"]
    assert "| ITEM 1. BUSINESS | 3 |" in sections[0]["text"]
    assert sections[1]["text"] == "We make chips."
    assert "| | 2022 | 2021 |" in sections[2]["text"]
    assert "| Revenue | $1,234 | $(56) |" in sections[2]["text"]
    assert "missing Item 1A" in warnings


def test_stray_item_line_after_part_iii_does_not_steal_item_1():
    lines = [
        "Item 1. Business",  # real heading
        "We make cereal.",
        "Item 1A. Risk Factors",
        "Risks.",
        "Item 10. Directors",
        "Item 1. of this report lists our executive officers.",  # stray line
        "Item 16. Form 10-K Summary",
        "None.",
    ]
    sections, _ = split_sections(lines)
    assert [s["item"] for s in sections] == ["1", "1A", "10", "16"]
    assert sections[0]["text"] == "We make cereal."


def test_item_8_stub_points_to_where_statements_are():
    lines = [
        "Item 7. MD&A",
        "| Total assets | $92,187 |",
        "Item 8. Financial Statements",
        "See Item 15.",
    ]
    _, warnings = split_sections(lines)
    assert warnings[-1] == "note: financial statements are under Item 7"


def test_table_keeps_columns_aligned_when_a_row_skips_a_cell():
    html = b"""<table>
      <tr><td></td><td>Location</td><td colspan="2">2022</td><td colspan="2">2021</td></tr>
      <tr><td>Contracts</td><td>Prepaid expenses</td><td>$</td><td>54</td><td>$</td><td>15</td></tr>
      <tr><td>Total assets</td><td></td><td>$</td><td>139</td><td>$</td><td>461</td></tr>
      <tr><td>Liabilities:</td></tr>
    </table>"""
    assert html_to_lines(html) == [
        "| | Location | 2022 | 2021 |",
        "| --- | --- | --- | --- |",
        "| Contracts | Prepaid expenses | $54 | $15 |",
        "| Total assets | | $139 | $461 |",
        "| Liabilities: | | | |",
    ]
