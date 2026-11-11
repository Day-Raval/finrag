from fastapi.testclient import TestClient

from finrag.answering import pipeline
from finrag.app import server

CFG = {
    "retrieval": {"filter": True},
    "corpus": {"tickers": ["KO"], "years": [2021, 2022]},
    "index": {"collection": "fixed_512_64_hdr"},
    "generation": {"prompt": "prompts/answer_v1.md", "model": "openai/gpt-oss-120b"},
    "experiment": "configs/hdr_hf_decomp_company.yaml",
}
CHUNK = {"chunk_id": "KO_2022:8:0001", "doc_id": "KO_2022", "item": "8", "score": 0.031,
         "company": "COCA COLA CO", "fiscal_year": 2022, "title": "Financial Statements",
         "text": "Total assets 92,763"}  # fmt: skip


def fake_answer(question, cfg, text=False):
    assert text, "the app must ask for chunk text"
    return {"answer": "Total assets were $92,763 million [KO, 2022, Item 8].", "retrieved": [CHUNK],
            "retrieve_s": 0.4, "latency_s": 21.0, "total_s": 21.4, "prompt_tokens": 2900,
            "completion_tokens": 120, "cached": False}  # fmt: skip


def client(monkeypatch, answer=fake_answer):
    monkeypatch.setattr(server, "config", lambda: CFG)
    monkeypatch.setattr(server, "answer", answer)
    return TestClient(server.app)


def test_ask_returns_answer_with_trace(monkeypatch):
    r = client(monkeypatch).post("/ask", json={"question": "  Coca-Cola FY2022 total assets?  "})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"].startswith("Total assets")
    assert body["filter"] == {"ticker": ["KO"], "fiscal_year": [2022]}
    assert body["retrieved"][0]["text"] == "Total assets 92,763"
    assert body["config"] == "configs/hdr_hf_decomp_company.yaml" and body["server_s"] >= 0


def test_ask_rejects_too_short_or_too_long_questions(monkeypatch):
    c = client(monkeypatch)
    assert c.post("/ask", json={"question": "hi"}).status_code == 422
    assert c.post("/ask", json={"question": "x" * 501}).status_code == 422
    assert c.post("/ask", json={}).status_code == 422


def test_pipeline_errors_become_502_with_a_message(monkeypatch):
    def broken(question, cfg, text=False):
        raise RuntimeError("Groq rate limit")

    r = client(monkeypatch, broken).post("/ask", json={"question": "Coca-Cola FY2022 total assets?"})
    assert r.status_code == 502 and "Groq rate limit" in r.json()["detail"]


def test_page_assets_and_health(monkeypatch):
    c = client(monkeypatch)
    page = c.get("/")
    assert page.status_code == 200 and "/static/app.js" in page.text
    assert "/ask" in c.get("/static/app.js").text and c.get("/static/app.css").status_code == 200
    assert "tieOut" in c.get("/static/tieout.js").text and "/static/tieout.js" in page.text
    health = c.get("/health").json()
    assert health["collection"] == "fixed_512_64_hdr" and health["model"] == "openai/gpt-oss-120b"
    assert health["companies"] == [{"ticker": "KO", "name": "Coca-Cola"}] and health["years"] == [2021, 2022]


def test_plan_returns_scope_without_searching(monkeypatch):
    def no_answer(question, cfg, text=False):
        raise AssertionError("/plan must not search or call the LLM")

    c = client(monkeypatch, no_answer)
    assert c.post("/plan", json={"question": "Coca Cola FY22 margin?"}).json() == {"filter": {"ticker": ["KO"], "fiscal_year": [2022]}}
    assert c.post("/plan", json={"question": "hi"}).status_code == 422


def test_pipeline_returns_chunk_text_only_when_asked(monkeypatch):
    monkeypatch.setattr(pipeline, "search", lambda q, cfg: [CHUNK])
    monkeypatch.setattr(pipeline, "generate", lambda q, chunks, cfg: {"answer": "a", "latency_s": 1.0})
    assert "text" not in pipeline.answer("q", {})["retrieved"][0]  # saved runs stay small
    assert pipeline.answer("q", {}, text=True)["retrieved"][0]["text"] == "Total assets 92,763"


def test_startup_warms_up_search_and_survives_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "config", lambda: CFG)
    monkeypatch.setattr(server, "answer", fake_answer)
    monkeypatch.setattr(server, "search", lambda q, cfg: calls.append(q))
    with TestClient(server.app) as c:  # entering the client runs startup
        assert c.get("/health").status_code == 200
    assert calls == ["warm-up"]

    def broken(q, cfg):
        raise FileNotFoundError("no index")

    monkeypatch.setattr(server, "search", broken)
    with TestClient(server.app) as c:  # a missing index must not stop the app
        assert c.get("/").status_code == 200
        assert c.get("/health").status_code == 200