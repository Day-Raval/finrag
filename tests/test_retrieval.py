import json

import numpy as np

from finrag.retrieval import dense, hybrid, search
from finrag.retrieval.filters import matches, question_filter

CFG = {"corpus": {"tickers": ["KO", "JNJ", "AXP", "MMM", "PEP"], "years": [2021, 2022]}}


def test_question_filter_reads_company_and_year():
    f = question_filter
    assert f("What is Coca Cola's FY2022 operating margin?", CFG) == {"ticker": ["KO"], "fiscal_year": [2022]}
    assert f("JnJ's FY22 free cash flow?", CFG) == {"ticker": ["JNJ"], "fiscal_year": [2022]}
    assert f("Did AMEX grow from FY 2021 to fiscal 2022?", CFG) == {"ticker": ["AXP"], "fiscal_year": [2021, 2022]}
    assert f("3M FY'21 capex vs PepsiCo", CFG) == {"ticker": ["MMM", "PEP"], "fiscal_year": [2021]}
    # out-of-corpus years and unknown companies -> no filter on that field
    assert f("What is Apple's FY2023 guidance?", CFG) == {"ticker": [], "fiscal_year": []}
    assert f("Who sells smokes?", CFG)["ticker"] == []


def test_matches_ignores_empty_fields():
    chunk = {"ticker": "KO", "fiscal_year": 2022}
    assert matches(chunk, None) and matches(chunk, {"ticker": [], "fiscal_year": []})
    assert matches(chunk, {"ticker": ["KO"], "fiscal_year": []})
    assert not matches(chunk, {"ticker": ["KO"], "fiscal_year": [2021]})


def test_rrf_rewards_chunks_both_lists_rank():
    a, b, c = ({"chunk_id": x} for x in "abc")
    fused = hybrid.rrf([[a, b], [c, b]], k=3)
    assert [x["chunk_id"] for x in fused] == ["b", "a", "c"]  # b in both lists wins
    assert fused[0]["score"] == round(1 / 62 + 1 / 62, 4)


def chunk(cid, ticker, year, text):
    return {"chunk_id": cid, "doc_id": f"{ticker}_{year}", "ticker": ticker, "company": ticker,
            "fiscal_year": year, "item": "7", "title": "MD&A", "text": text}  # fmt: skip


def test_hybrid_search_end_to_end(tmp_path, monkeypatch):
    chunks = [
        chunk("KO_2022:7:0000", "KO", 2022, "Total assets were $92,763 million."),
        chunk("KO_2021:7:0000", "KO", 2021, "Total assets were $94,354 million."),
        chunk("PEP_2022:7:0000", "PEP", 2022, "Net revenue grew 8.7 percent."),
    ]
    path = tmp_path / "{collection}.jsonl"
    (tmp_path / "c.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks))
    vec = {c["chunk_id"]: np.eye(3)[i] for i, c in enumerate(chunks)}
    # fake embedder: every question points at the PEP chunk, so dense alone is wrong
    monkeypatch.setattr(dense, "embed", lambda texts, model: [np.eye(3)[2] for _ in texts])
    cfg = {
        **CFG,
        "embedding": {"model": "fake"},
        "chunking": {"header": True},
        "index": {"chunks": str(path), "collection": "c", "qdrant_path": str(tmp_path / "q")},
        "retrieval": {"top_k": 2, "hybrid": True, "filter": True, "candidates": 3},
    }
    from qdrant_client.models import Distance, PointStruct, VectorParams

    client = dense.get_client(cfg["index"]["qdrant_path"])
    client.create_collection("c", vectors_config=VectorParams(size=3, distance=Distance.COSINE))
    client.upsert("c", [PointStruct(id=i, vector=vec[c["chunk_id"]].tolist(), payload=c) for i, c in enumerate(chunks)])

    hits = search("Coca Cola total assets in FY2022?", cfg)
    assert hits[0]["chunk_id"] == "KO_2022:7:0000"  # filter + BM25 beat the misled dense
    assert all(h["ticker"] == "KO" and h["fiscal_year"] == 2022 for h in hits)

    cfg["retrieval"] = {"top_k": 1}  # plain dense, unchanged default
    assert search("Coca Cola total assets in FY2022?", cfg)[0]["chunk_id"] == "PEP_2022:7:0000"
    dense.get_client.cache_clear()


class FakeCrossEncoder:
    """Scores a pair by whether the chunk contains the question's last word."""

    def predict(self, pairs, batch_size):
        return [float(q.split()[-1].strip("?") in text) for q, text in pairs]


def test_rerank_reorders_and_trims(monkeypatch):
    from finrag.retrieval import reranker as rr

    monkeypatch.setattr(rr, "get_model", lambda name: FakeCrossEncoder())
    cfg = {"chunking": {"header": False}, "retrieval": {"reranker": "fake"}}
    chunks = [chunk(f"c{i}", "KO", 2022, t) for i, t in enumerate(["revenue", "dividends", "capex"])]
    out = rr.rerank("What was capex?", chunks, cfg, k=2)
    assert [c["chunk_id"] for c in out] == ["c2", "c0"]  # match first, then original order
    assert out[0]["score"] == 1.0
    assert rr.rerank("q", [], cfg, k=2) == []


def test_search_reranks_a_wider_pool(monkeypatch):
    from finrag import retrieval

    seen = {}

    def fake_dense(question, cfg, k, flt):
        seen["k"] = k
        return [{"chunk_id": str(i)} for i in range(k)]

    monkeypatch.setattr(retrieval.dense, "search", fake_dense)
    monkeypatch.setattr(retrieval, "rerank", lambda q, hits, cfg, k: hits[::-1][:k])
    cfg = {"retrieval": {"top_k": 3, "rerank": True, "candidates": 20}}
    out = retrieval.search("q", cfg)
    assert seen["k"] == 20 and [c["chunk_id"] for c in out] == ["19", "18", "17"]