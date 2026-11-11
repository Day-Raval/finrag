// Unit tests for the UI's tie-out. Run: node --test tests/tieout.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { tieOut } = require("../src/finrag/app/static/tieout.js");

const statuses = (r) => r.figures.map((f) => [f.value, f.status]);

test("rounded billions tie, and figures computed from them are calculated", () => {
  // the real Verizon answer from the app, against its income-statement excerpt
  const answer = "Verizon's net income fell from $22.6 billion in FY 2021 to $21.7 billion in FY 2022, " +
    "a decline of roughly $0.9 billion (about $870 million) year-over-year 【VERIZON COMMUNICATIONS INC, 2022, Item 7】.";
  const r = tieOut(answer, ["intro", "| Consolidated Net Income | $21,748 | $22,618 |\n| Provision for income taxes | 6,523 | 6,802 |"]);
  assert.deepEqual(statuses(r), [
    ["22.6 billion", "tied"], ["21.7 billion", "tied"], ["0.9 billion", "calc"], ["870 million", "calc"],
  ]);
  assert.equal(r.figures[3].formula, "22,618 − 21,748");
  assert.deepEqual(r.figures[0].srcs, [1]);
  assert.ok(r.marks.has("22618") && r.marks.has("21748"));
});

test("exact figures tie exactly; years, citations and refusals are not figures", () => {
  const r = tieOut("Total assets were **$92,763 million** in 2022 [KO, 2022, Item 8].", ["Total assets 92,763 and 94,354"]);
  assert.deepEqual(statuses(r), [["92,763 million", "tied"]]);
  assert.equal(tieOut("Not found in the filings.", ["92,763"]).figures.length, 0);
  // plain figures need an exact match: 11% must not tie to 11.4
  assert.equal(tieOut("Revenue grew 11%.", ["grew 11.4% in 2022"]).figures[0].status, "flag");
});

test("1.046 billion ties to 1,046 million", () => {
  const r = tieOut("Capex was $1.046 billion.", ["purchases of PP&E were $1,046 million"]);
  assert.equal(r.figures[0].status, "tied");
});

test("percent change is calculated only from figures the answer tied", () => {
  const r = tieOut("Revenue rose from $38,655 million to $43,004 million, up 11.3%.", ["$ 43,004 | $ 38,655"]);
  assert.deepEqual(statuses(r), [["38,655 million", "tied"], ["43,004 million", "tied"], ["11.3%", "calc"]]);
  // 100 = 600 - 500, but the answer never cited 600 or 500, so it stays flagged
  assert.equal(tieOut("A gap of $100 million.", ["600 and 500"]).figures[0].status, "flag");
});