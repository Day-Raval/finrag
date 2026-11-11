"""Standard FastAPI app over the answer pipeline, with a trace for every answer.

POST /ask {"question": "..."} returns the answer and its trace: the companies and
years the filter read, each retrieved chunk (score, filing, Item, text), retrieval
and generation time, token counts, and whether the answer came from the cache.
POST /plan returns the same filter instantly, so the UI can show the search scope
while the question is typed. GET / serves the UI (static/ holds its CSS and JS);
GET /health reports the loaded config, model and coverage.
"""

import logging
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from finrag.answering.pipeline import answer
from finrag.config import load_config
from finrag.evaluation.build_golden import TICKERS
from finrag.retrieval import search
from finrag.retrieval.filters import question_filter

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the embedding model, BM25 index and Qdrant client before the first
    # question: cold, the first search takes ~40 s instead of ~0.5 s.
    try:
        start = time.perf_counter()
        search("warm-up", config())
        log.info("Search warmed up in %.1f s", time.perf_counter() - start)
    except Exception:  # the app still starts; the first question pays the cost
        log.exception("Warm-up failed; the first question will load search itself")
    yield


app = FastAPI(title="Annualyst", description="Grounded Q&A over SEC 10-K filings", lifespan=lifespan)
HERE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
NAMES = {ticker: name for name, ticker in TICKERS.items()}


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@lru_cache(maxsize=1)
def config() -> dict:
    load_dotenv()
    return load_config()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (HERE / "index.html").read_text()


@app.get("/health")
def health() -> dict:
    cfg = config()
    return {
        "status": "ok",
        "config": cfg.get("experiment", "config.yaml"),
        "collection": cfg["index"]["collection"],
        "prompt": cfg["generation"]["prompt"],
        "model": cfg["generation"]["model"],
        "years": cfg["corpus"]["years"],
        "companies": [{"ticker": t, "name": NAMES.get(t, t)} for t in cfg["corpus"]["tickers"]],
    }


@app.post("/plan")
def plan(req: Ask) -> dict:
    """The companies and fiscal years the filter reads from the question; no search, no LLM."""
    cfg = config()
    return {"filter": question_filter(req.question, cfg) if cfg["retrieval"].get("filter") else None}


# shortcut: sync handler on one shared local Qdrant client, fine for one local
# user; move to Qdrant server mode before serving concurrent users
@app.post("/ask")
def ask(req: Ask) -> dict:
    cfg = config()
    question = req.question.strip()
    start = time.perf_counter()
    try:
        out = answer(question, cfg, text=True)
    except Exception as e:  # Groq, network or index errors: a message, not a stack trace
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}") from e
    return {
        **out,
        "server_s": round(time.perf_counter() - start, 2),
        "filter": question_filter(question, cfg) if cfg["retrieval"].get("filter") else None,
        "config": cfg.get("experiment", "config.yaml"),
    }