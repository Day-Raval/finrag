"""Disk cache for LLM calls: an identical request returns the saved response.

The key covers model, full prompt and settings, so any change to the question,
retrieved chunks, prompt template or model is a cache miss. Lives under data/
(gitignored). Delete data/cache/ to force fresh calls.
"""

import hashlib
import json
from pathlib import Path

CACHE_DIR = Path("data/cache/llm")


def _path(request: dict) -> Path:
    digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def get(request: dict) -> dict | None:
    path = _path(request)
    return json.loads(path.read_text()) if path.exists() else None


def put(request: dict, response: dict) -> None:
    path = _path(request)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(response))
    tmp.replace(path)  # no half-written cache entry if interrupted