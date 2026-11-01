import yaml

from finrag.config import load_config, merge


def test_merge_overrides_only_given_keys():
    base = {
        "chunking": {"strategy": "fixed", "size": 512, "overlap": 64},
        "runs_dir": "r",
    }
    out = merge(base, {"chunking": {"strategy": "section"}})
    assert out == {
        "chunking": {"strategy": "section", "size": 512, "overlap": 64},
        "runs_dir": "r",
    }
    assert base["chunking"]["strategy"] == "fixed"  # base not mutated


def test_every_experiment_config_loads(monkeypatch):
    from pathlib import Path

    for path in sorted(Path("configs").glob("*.yaml")):
        monkeypatch.setenv("FINRAG_CONFIG", str(path))
        cfg = load_config()
        assert cfg["index"]["collection"] == path.stem, path  # file name = collection
        assert cfg["chunking"]["strategy"] in ("fixed", "section"), path
        assert cfg["index"]["qdrant_path"] and cfg["golden"]["path"]  # base keys kept
        assert yaml.safe_dump(cfg)  # run_golden can save the snapshot