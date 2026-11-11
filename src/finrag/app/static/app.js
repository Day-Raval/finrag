// Annualyst UI: live scope, ask, figure check, timing, evidence, session history.
// The tie-out itself (tied / calculated / flagged) lives in tieout.js.
const $ = (id) => document.getElementById(id);
const make = (tag, props = {}, ...kids) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...kids);
  return node;
};

const { tieOut, NUM, plain } = window.Tieout;   // static/tieout.js
const HISTORY_KEY = "annualyst.history.v1";

const state = { companies: [], names: {}, history: loadHistory(), current: null };

/* ---------- startup ---------- */

async function init() {
  applyTheme(readPref("annualyst.theme"));
  try {
    const h = await (await fetch("/health")).json();
    $("health").classList.add("live");
    $("health-text").textContent = `Live on ${h.model.replace(/^.*\//, "")}`;
    $("health").title = `Config ${h.config}, prompt ${h.prompt}`;
    state.companies = h.companies;
    state.names = Object.fromEntries(h.companies.map((c) => [c.ticker, c.name]));
    $("coverage-note").textContent = `${h.companies.length} companies, fiscal ${h.years[0]}–${h.years.at(-1)}. Open one for questions to ask.`;
    renderCompanies(h.years.at(-1));
  } catch {
    $("health").classList.add("down");
    $("health-text").textContent = "Server not reachable";
  }
  renderHistory();
  renderScope(null);
}

/* ---------- theme ---------- */

function applyTheme(theme) {
  const dark = theme ? theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  if (theme) document.documentElement.dataset.theme = theme;
  $("theme").dataset.dark = String(dark);
  $("theme").setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
}
$("theme").addEventListener("click", () => {
  const dark = document.documentElement.dataset.theme
    ? document.documentElement.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  const next = dark ? "light" : "dark";
  writePref("annualyst.theme", next);
  applyTheme(next);
});

/* ---------- coverage rail ---------- */

function renderCompanies(year) {
  $("companies").replaceChildren(...state.companies.map(({ ticker, name }) => {
    const qs = [
      `What was ${name}'s total revenue in FY${year}?`,
      `How did ${name}'s net income change from FY${year - 1} to FY${year}?`,
      `What were ${name}'s capital expenditures in FY${year}?`,
    ];
    return make("details", { className: "company" },
      make("summary", {},
        make("span", { className: "tk", textContent: ticker }),
        make("span", { className: "nm", textContent: name }),
        make("span", { className: "chev", textContent: "›", ariaHidden: "true" })),
      make("ul", {}, ...qs.map((q) => make("li", {}, make("button", {
        type: "button", textContent: q, onclick: () => { closeRail(); ask(q); },
      })))));
  }));
}

$("rail-toggle").addEventListener("click", () => {
  const open = $("rail").classList.toggle("open");
  $("rail-toggle").setAttribute("aria-expanded", String(open));
});
function closeRail() {
  $("rail").classList.remove("open");
  $("rail-toggle").setAttribute("aria-expanded", "false");
}

/* ---------- composer: autosize, live scope, shortcuts ---------- */

const q = $("q");
let planTimer, planSeq = 0;
q.addEventListener("input", () => {
  q.style.height = "auto";
  q.style.height = `${q.scrollHeight}px`;
  clearTimeout(planTimer);
  planTimer = setTimeout(plan, 250);
});
q.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $("form").requestSubmit(); }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== q && !e.ctrlKey && !e.metaKey) { e.preventDefault(); q.focus(); }
  if (e.key === "Escape") closeRail();
});

async function plan() {
  const text = q.value.trim();
  if (text.length < 3) return renderScope(null);
  const seq = ++planSeq;
  try {
    const r = await fetch("/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: text }) });
    if (r.ok && seq === planSeq) renderScope((await r.json()).filter, true);
  } catch { /* scope preview is optional */ }
}

function scopeChips(f) {
  if (!f) return [];
  const chips = f.ticker.map((t) => make("span", { className: "chip" }, make("b", { textContent: t }), state.names[t] || ""));
  chips.push(make("span", { className: "chip", textContent: f.fiscal_year.length ? `Fiscal ${f.fiscal_year.join(" and ")}` : "Both years" }));
  if (!f.ticker.length) chips.unshift(make("span", { className: "chip", textContent: "All companies" }));
  return chips;
}

function renderScope(f, typed = false) {
  const box = $("scope");
  if (!typed) return box.replaceChildren(make("span", { textContent: "Names a company and year? The search narrows to those filings." }));
  box.replaceChildren(make("span", { textContent: "Will search" }), ...scopeChips(f));
}

/* ---------- ask ---------- */

for (const b of document.querySelectorAll(".starter")) b.addEventListener("click", () => ask(b.textContent));
$("form").addEventListener("submit", (e) => { e.preventDefault(); ask(q.value); });

async function ask(question) {
  question = question.trim();
  q.value = question;
  q.dispatchEvent(new Event("input"));
  const status = $("status");
  if (question.length < 3) {
    status.textContent = "Type a question of at least 3 characters.";
    status.classList.add("error");
    return;
  }
  $("go").disabled = true;
  status.classList.remove("error");
  $("welcome").hidden = true;
  $("results").hidden = true;
  $("loading").hidden = false;
  const started = Date.now();
  const tick = () => { status.textContent = `Searching the filings and writing the answer, ${Math.round((Date.now() - started) / 1000)} s`; };
  tick();
  const timer = setInterval(tick, 1000);
  try {
    const r = await fetch("/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
    const d = await r.json().catch(() => ({}));
    if (r.status === 422) throw new Error("Questions need 3 to 500 characters.");
    if (!r.ok) throw new Error(`No answer: ${d.detail || r.statusText}. Check the server terminal, then try again.`);
    const entry = { question, at: Date.now(), result: d };
    state.history = [entry, ...state.history.filter((h) => h.question !== question)].slice(0, 20);
    saveHistory();
    show(entry);
    status.textContent = "";
  } catch (err) {
    status.textContent = err.message;
    status.classList.add("error");
    if (!state.current) $("welcome").hidden = false; else $("results").hidden = false;
  } finally {
    clearInterval(timer);
    $("loading").hidden = true;
    $("go").disabled = false;
  }
}

/* ---------- render ---------- */

function show(entry) {
  state.current = entry;
  const d = entry.result;
  const t = tieOut(d.answer, d.retrieved.map((c) => c.text));
  $("welcome").hidden = true;
  $("asked").textContent = entry.question;

  // answer with every figure marked: tied, calculated, or flagged
  $("answer").replaceChildren(...t.parts.map((f) => {
    if (typeof f === "string") return f;
    const node = make("span", { className: `fig ${f.status}`, textContent: f.raw, id: `fig-${f.i}` });
    node.title = {
      tied: `Found in excerpt ${f.srcs.map((i) => i + 1).join(", ")}${f.matched[0] === f.raw ? "" : ` as ${f.matched[0]}`}`,
      calc: `Calculated from the excerpts: ${f.formula}`,
      flag: "Not found in the excerpts and not calculable from the figures cited; check it",
    }[f.status];
    if (f.status !== "flag") {
      node.tabIndex = 0;
      bindLight(node, f.srcs);
      node.addEventListener("click", () => jump(f.srcs[0]));
    }
    return node;
  }));

  // tie-out summary
  const total = t.figures.length;
  const seg = (cls, n) => make("span", { className: cls, style: `width:${(n / total) * 100}%` });
  $("tie-bar").replaceChildren(...(total ? [seg("t", t.tied), seg("c", t.calc), seg("f", t.flagged)] : []));
  $("tie-bar").hidden = !total;
  const tt = $("tie-text");
  const traced = [t.tied && `${t.tied} found in the excerpts`, t.calc && `${t.calc} calculated from them`].filter(Boolean).join(", ");
  if (t.refused) tt.replaceChildren("No excerpt answered this question, so no figures were stated.");
  else if (!total) tt.replaceChildren("This answer states no figures to check.");
  else if (!t.flagged) tt.replaceChildren(make("b", { className: "ok", textContent: total === 1 ? "The figure checks out" : `All ${total} figures check out` }), `: ${traced}. Point at one to see its source.`);
  else tt.replaceChildren(make("b", { className: "warn", textContent: `${t.flagged} of ${total} figure${total === 1 ? "" : "s"}` }), ` can't be traced to the excerpts${traced ? ` (${traced})` : ""}. Check ${t.flagged === 1 ? "it" : "them"} before use.`);

  // figure check table
  $("figures-panel").hidden = !total;
  const links = (srcs) => srcs.flatMap((i, k) => [k ? ", " : "", make("button", { type: "button", className: "src-link", textContent: `Excerpt ${i + 1}`, onclick: () => jump(i) })]);
  $("figures").replaceChildren(...t.figures.map((f) => {
    const found = {
      tied: [...links(f.srcs), ...(f.matched[0] === f.raw ? [] : [make("span", { className: "as", textContent: ` as ${f.matched[0]}` })])],
      calc: [make("span", { className: "formula", textContent: f.formula }), make("br"), ...links(f.srcs)],
      flag: ["Not traceable"],
    }[f.status];
    const tr = make("tr", { className: f.status },
      make("td", { textContent: f.value }),
      make("td", { className: "ctx", textContent: f.context }),
      make("td", {}, ...found));
    if (f.status !== "flag") bindLight(tr, f.srcs, f.i);
    return tr;
  }));

  // timing + details
  const gen = d.cached ? 0 : d.latency_s, totalS = Math.max(d.retrieve_s + gen, 0.01);
  $("timeline").replaceChildren(
    span("Retrieval", d.retrieve_s, totalS),
    span(d.cached ? "Answer (cache)" : "Answer", d.cached ? 0 : gen, totalS, d.cached));
  const f = d.filter;
  const rows = [
    ["Searched", f ? [f.ticker.map((x) => state.names[x] || x).join(" and ") || "All companies", f.fiscal_year.length ? `fiscal ${f.fiscal_year.join(" and ")}` : "both years"].join(", ") : "All filings"],
    ["Tokens", `${d.prompt_tokens.toLocaleString()} in, ${d.completion_tokens.toLocaleString()} out`],
    ["Configuration", (d.config || "").replace(/^configs\//, "").replace(/\.yaml$/, "")],
    ["Asked", new Date(entry.at).toLocaleString()],
  ];
  $("details").replaceChildren(...rows.flatMap(([k, v]) => [make("dt", { textContent: k }), make("dd", { textContent: v })]));

  // evidence
  const top = Math.max(...d.retrieved.map((c) => c.score), 1e-9);
  $("evidence-count").textContent = `${d.retrieved.length} excerpts, by relevance`;
  $("sources").replaceChildren(...d.retrieved.map((c, i) => source(c, i, top, t.marks)));

  $("results").hidden = false;
  renderHistory();
  $("asked").focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function span(label, seconds, total, cache = false) {
  return make("div", { className: `span-row${cache ? " cache" : ""}` },
    make("span", { textContent: label }),
    make("div", { className: "track" }, make("div", { className: "fill", style: `width:${Math.max((seconds / total) * 100, seconds ? 1.5 : 0)}%` })),
    make("span", { className: "sec", textContent: cache ? "0 s" : `${seconds} s` }));
}

function bindLight(node, srcs, figIndex) {
  const light = (on) => {
    srcs.forEach((i) => $(`src-${i}`)?.classList.toggle("lit", on));
    if (figIndex !== undefined) $(`fig-${figIndex}`)?.classList.toggle("on", on);
  };
  for (const [ev, on] of [["mouseenter", true], ["mouseleave", false], ["focusin", true], ["focusout", false]]) node.addEventListener(ev, () => light(on));
}

function jump(i) {
  const src = $(`src-${i}`);
  src.scrollIntoView({ block: "nearest", behavior: "smooth" });
  src.classList.add("lit");
  setTimeout(() => src.classList.remove("lit"), 1200);
}

function source(c, i, top, answerFigs) {
  const [ticker, year] = (c.doc_id || "").split("_");
  const body = make("div", { className: "excerpt", id: `ex-${i}` });
  renderExcerpt(body, c.text || "", answerFigs);
  const open = body.querySelector("mark") !== null;    // excerpts the answer drew figures from start open
  body.classList.toggle("open", open);
  const more = make("button", { type: "button", className: "more", textContent: open ? "Show less" : "Show whole excerpt" });
  more.setAttribute("aria-expanded", String(open));
  more.setAttribute("aria-controls", body.id);
  more.addEventListener("click", () => {
    const isOpen = body.classList.toggle("open");
    more.setAttribute("aria-expanded", String(isOpen));
    more.textContent = isOpen ? "Show less" : "Show whole excerpt";
  });
  return make("article", { className: "src", id: `src-${i}` },
    make("div", { className: "src-head" },
      make("span", { className: "rank", textContent: i + 1 }),
      make("h3", { textContent: `${state.names[ticker] || ticker} 10‑K, fiscal ${year}, Item ${c.item}` }),
      ...(c.title ? [make("span", { className: "item", textContent: c.title })] : []),
      make("div", { className: "rel" },
        make("div", { className: "track" }, make("div", { className: "fill", style: `width:${(c.score / top) * 100}%` })),
        make("span", { textContent: `relevance ${Number(c.score).toFixed(3)}` }))),
    body, more);
}

// Excerpts are Markdown: paragraphs plus pipe tables. Figures the answer used are marked.
function renderExcerpt(box, text, answerFigs) {
  let table = null;
  for (const line of text.split("\n")) {
    if (/^\s*\|?\s*$/.test(line)) continue;            // blank or a lone "|" left by a chunk cut
    if (line.split("|").length >= 3) {                 // a table row, even one a chunk boundary cut in half
      if (/^\|?\s*:?-{3}/.test(line.trim())) continue;  // separator row
      table ??= box.appendChild(make("table"));
      const tr = table.insertRow();
      for (const cell of line.trim().replace(/^\||\|$/g, "").split("|")) withMarks(tr.insertCell(), cell.trim(), answerFigs);
    } else {
      table = null;
      if (line.trim()) withMarks(box.appendChild(make("p")), line, answerFigs);
    }
  }
}

function withMarks(node, text, answerFigs) {
  let last = 0;
  for (const m of text.matchAll(NUM)) {
    if (!answerFigs.has(plain(m[0]))) continue;
    node.append(text.slice(last, m.index), make("mark", { textContent: m[0] }));
    last = m.index + m[0].length;
  }
  node.append(text.slice(last));
}

/* ---------- copy ---------- */

async function copy(text, done) {
  try { await navigator.clipboard.writeText(text); toast(done); }
  catch { toast("Copy isn't allowed here. Select the text instead."); }
}
$("copy-answer").addEventListener("click", () => state.current && copy(state.current.result.answer, "Copied answer"));
$("copy-trace").addEventListener("click", () => state.current && copy(JSON.stringify({ question: state.current.question, ...state.current.result }, null, 2), "Copied trace as JSON"));

let toastTimer;
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 1800);
}

/* ---------- session history (this browser only) ---------- */

function renderHistory() {
  $("history-empty").hidden = state.history.length > 0;
  $("history").replaceChildren(...state.history.map((h) => {
    const t = tieOut(h.result.answer, h.result.retrieved.map((c) => c.text));
    const total = t.figures.length, ok = t.tied + t.calc;
    const pill = t.refused || !total ? make("span", { className: "pill none", textContent: t.refused ? "No answer" : "No figures" })
      : make("span", { className: `pill ${ok === total ? "ok" : "warn"}`, textContent: `${ok}/${total} traced` });
    const b = make("button", { type: "button", onclick: () => { closeRail(); show(h); } }, make("span", { className: "hq", textContent: h.question }), pill);
    b.setAttribute("aria-current", String(state.current === h));
    return make("li", {}, b);
  }));
}

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; } catch { return []; }
}
function saveHistory() {
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(state.history)); } catch { /* storage is a convenience */ }
}
function readPref(k) { try { return localStorage.getItem(k); } catch { return null; } }
function writePref(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } }

init();