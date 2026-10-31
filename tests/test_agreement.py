from finrag.evaluation.agreement import cohens_kappa
from finrag.evaluation.label import sample


def test_cohens_kappa():
    assert cohens_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert cohens_kappa([1, 0, 1, 0], [1, 1, 0, 0]) == 0.0  # no better than chance
    assert cohens_kappa([1, 1, 1, 1], [1, 1, 1, 1]) == 1.0  # all one class
    # 8/10 agree, both raters say "pass" half the time -> kappa 0.6
    a = [1] * 5 + [0] * 5
    b = [1] * 4 + [0] + [1] + [0] * 4
    assert round(cohens_kappa(a, b), 2) == 0.6


def test_sample_is_stable_and_skips_unanswerable():
    answers = [
        {
            "id": f"q{i}",
            "category": "numeric",
            "answer": "Not found in the filings." if i % 2 else "$5",
        }
        for i in range(40)
    ] + [
        {"id": "u1", "category": "unanswerable", "answer": "Not found in the filings."}
    ]
    first, second = sample(answers), sample(answers)
    assert first == second and len(first) == 20
    assert sum(a["answer"] == "$5" for a in first) == 16
    assert all(a["category"] != "unanswerable" for a in first)