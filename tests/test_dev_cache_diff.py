import json
import types

import finrag.generation.answer as answer_mod
from finrag.evaluation.diff import compare
from finrag.evaluation.make_dev import PER_CATEGORY, dev_subset
from finrag.generation import cache


def test_dev_subset_is_stable_and_covers_every_category():
    golden = [
        {"id": f"{c}_{i}", "category": c} for c in PER_CATEGORY for i in range(10)
    ]
    first, second = dev_subset(golden), dev_subset(golden)
    assert first == second and len(first) == 24
    assert {g["category"] for g in first} == set(PER_CATEGORY)


def test_generate_reuses_cached_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    calls = []

    def create(**request):
        calls.append(request)
        usage = types.SimpleNamespace(prompt_tokens=100, completion_tokens=10)
        message = types.SimpleNamespace(content="$92,763 million")
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=message)], usage=usage
        )

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    monkeypatch.setattr(answer_mod, "get_client", lambda: client)
    prompt = tmp_path / "p.md"
    prompt.write_text("{context}\nQ: {question}")
    cfg = {"generation": {"model": "m", "prompt": str(prompt), "temperature": 0}}
    chunk = {"company": "KO", "fiscal_year": 2022, "item": "8", "text": "assets"}

    first = answer_mod.generate("Total assets?", [chunk], cfg)
    second = answer_mod.generate("Total assets?", [chunk], cfg)
    third = answer_mod.generate("Total debt?", [chunk], cfg)  # new question -> new call
    assert len(calls) == 2
    assert (first["cached"], second["cached"], third["cached"]) == (False, True, False)
    assert second["answer"] == first["answer"] and second["prompt_tokens"] == 100


def test_compare_finds_regressions_and_improvements():
    a = {"q1": {"category": "numeric", "correctness": 1.0, "section_recall": 1.0},
         "q2": {"category": "numeric", "correctness": 0.0, "section_recall": 0.0},
         "u1": {"category": "unanswerable", "correctness": 1.0}}  # fmt: skip
    b = json.loads(json.dumps(a))
    b["q1"]["correctness"], b["q2"]["correctness"] = 0.5, 1.0
    table, worse, better = compare(a, b)
    assert worse == ["q1"] and better == ["q2"]
    assert table["correctness"] == (0.5, 0.75)  # unanswerable excluded