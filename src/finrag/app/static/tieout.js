// Tie-out: trace every figure in an answer back to the filing excerpts it came from.
//   tied:  the figure is in an excerpt (rounded billions count: "22.6 billion" ties to 22,618 million)
//   calc:  the figure is a difference, sum or % change of figures the answer itself tied
//   flag:  neither, so a reader should check it
// Loaded by the page (window.Tieout) and by Node for tests (module.exports).
(function (root) {
  const NUM = /\d[\d,]*(?:\.\d+)?/g;                 // 92,763  21.5  2022
  const CITE = /\[[^\]]*\]|【[^】]*】/g;               // [KO, 2022, Item 8]  【1, 2022, Item 7】
  const UNIT = /^\s*(%|percent|billion|million|thousand)?/i;
  const plain = (n) => n.replace(/,/g, "");
  const isFigure = (n) => plain(n).replace(".", "").length >= 2 && !/^(19|20)\d{2}$/.test(plain(n));
  const fmt = (v) => (Number.isInteger(v) ? v.toLocaleString("en-US") : v.toLocaleString("en-US", { maximumFractionDigits: 2 }));

  // Value in the filing's units (millions) and how far a rounded statement may be from it.
  function measure(raw, unit) {
    const decimals = (raw.split(".")[1] || "").length;
    const scale = /billion/i.test(unit) ? 1000 : 1;
    return { v: parseFloat(plain(raw)) * scale, round: 0.5 * 10 ** -decimals * scale + 1e-9, scale };
  }

  function tieOut(answer, excerpts) {
    const text = (answer || "").replace(/\*\*/g, "");    // drop Markdown bold markers
    const sources = excerpts.map((t, i) =>
      ((t || "").match(NUM) || []).filter(isFigure).map((raw) => ({ i, raw, v: parseFloat(plain(raw)) })));
    const cites = [...text.matchAll(CITE)].map((m) => [m.index, m.index + m[0].length]);
    const inCite = (i) => cites.some(([a, b]) => i >= a && i < b);
    const refused = /not found in the filings/i.test(text);
    const figures = [];

    // pass 1: tie each figure to excerpt values (exact; within rounding when stated in billions)
    for (const m of refused ? [] : text.matchAll(NUM)) {
      if (!isFigure(m[0]) || inCite(m.index)) continue;
      const end = m.index + m[0].length;
      const unit = text.slice(end, end + 14).match(UNIT)[0];
      const { v, round, scale } = measure(m[0], unit);
      // plain figures must match exactly; rounded billions need 3+ significant digits
      // ("22.6 billion" ±0.2%), since "0.9 billion" would match anything from 850 to 950
      const digits = plain(m[0]).replace(".", "").replace(/^0+/, "").length;
      const hits = scale > 1 && digits < 3 ? []
        : sources.flat().filter((s) => Math.abs(s.v - v) <= (scale > 1 ? round : 1e-9));
      const before = text.slice(Math.max(0, m.index - 80), m.index)
        .replace(CITE, " ").replace(/^[^[【]*[\]】]/, " ")     // drop whole and cut-off citations
        .replace(/\s+/g, " ").replace(/ ([,.;])/g, "$1").replace(/\$\s*$/, "").trim().split(" ").slice(-7).join(" ");
      figures.push({
        i: figures.length, raw: m[0], at: m.index, end, value: m[0] + unit.trimEnd(), context: `…${before}`,
        v, round, percent: /%|percent/i.test(unit),
        status: hits.length ? "tied" : "flag",
        srcs: [...new Set(hits.map((h) => h.i))], matched: hits.map((h) => h.raw), formula: null,
      });
    }

    // pass 2: an untied figure may be computed from figures the answer tied
    const operands = [];
    for (const f of figures.filter((x) => x.status === "tied")) {
      const s = sources.flat().find((x) => x.raw === f.matched[0]);
      if (!operands.some((o) => o.v === s.v)) operands.push(s);
    }
    for (const f of figures.filter((x) => x.status === "flag")) {
      search: for (const a of operands) {
        for (const b of operands) {
          if (a === b) continue;
          const tries = f.percent
            ? [[((a.v - b.v) / b.v) * 100, `(${fmt(a.v)} − ${fmt(b.v)}) / ${fmt(b.v)}`]]
            : [[a.v - b.v, `${fmt(a.v)} − ${fmt(b.v)}`], [a.v + b.v, `${fmt(a.v)} + ${fmt(b.v)}`]];
          for (const [value, formula] of tries) {
            if (Math.abs(Math.abs(value) - f.v) <= f.round) {
              Object.assign(f, { status: "calc", formula, srcs: [...new Set([a.i, b.i])], matched: [a.raw, b.raw] });
              break search;
            }
          }
        }
      }
    }

    const parts = [];
    let last = 0;
    for (const f of figures) {
      parts.push(text.slice(last, f.at), f);
      last = f.end;
    }
    parts.push(text.slice(last));
    const marks = new Set(figures.flatMap((f) => (f.status === "flag" ? [] : f.matched.map(plain))));
    const count = (s) => figures.filter((f) => f.status === s).length;
    return { parts, figures, marks, refused, tied: count("tied"), calc: count("calc"), flagged: count("flag") };
  }

  const api = { tieOut, NUM, plain };
  if (typeof module !== "undefined") module.exports = api;
  else root.Tieout = api;
})(this);