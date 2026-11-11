# App

This package serves Annualyst as a local web app: a FastAPI server over the
answer pipeline and a one-page research workspace.

```bash
python -m finrag.app        # http://127.0.0.1:8000
```

| Module | Responsibility |
| --- | --- |
| [`__main__.py`](__main__.py) | Start uvicorn on 127.0.0.1 with the final configuration unless `FINRAG_CONFIG` names another. |
| [`server.py`](server.py) | `POST /ask` (answer + trace), `POST /plan` (search scope, no LLM), `GET /health` (config, model, coverage), static files; warms search up at startup. |
| [`index.html`](index.html), [`static/app.css`](static/app.css), [`static/app.js`](static/app.js) | The workspace: coverage rail, session history, composer with live scope, answer, figure check, timing, evidence. |
| [`static/tieout.js`](static/tieout.js) | The figure tie-out, shared by the page and its Node tests. |

## How it works

- **Ask.** `/ask` runs the pipeline with chunk text included and returns the
  answer, the five excerpts (score, filing, Item, text), retrieval and generation
  time, token counts, whether the answer came from the LLM cache, the filter the
  question produced, and the config in use. Pipeline errors return 502 with a
  message; questions must be 3 to 500 characters.
- **Live scope.** While a question is typed, `/plan` returns the companies and
  fiscal years the filter reads from it, shown as chips under the box.
- **Figure tie-out.** Every figure in the answer is marked:
  - *found*: it appears in an excerpt; figures stated in billions with at least
    three significant digits tie to the millions they round from;
  - *calculated*: it is the difference, sum or % change of figures the answer
    itself tied, and the working is shown;
  - *not traceable*: neither, so check it.
  Years, citation text and refusals are not treated as figures. The rules are
  pinned by [`tests/tieout.test.js`](../../../tests/tieout.test.js).
- **Warm-up.** The embedding model, BM25 index and Qdrant client load at startup,
  so the first question costs about 0.5 s of search instead of about 40 s.
- **Session history.** Up to 20 answers are kept in the browser's local storage
  and reopen without another call.

## Limitations

- Local and single-user: it listens on 127.0.0.1, has no authentication, and
  shares one embedded Qdrant client; every question spends Groq tokens.
- The tie-out matches figures as written. A correct figure rounded below three
  significant digits, or derived by a ratio such as a margin, shows as not
  traceable unless a difference, sum or % change of cited figures explains it.
- Excerpts are assumed to be in millions when converting billions; filings
  reported in thousands would not tie.
- Fonts load from Google Fonts; offline, the page falls back to system fonts.