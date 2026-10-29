"""Find lines in a parsed filing, to fill in answers for evals/custom.jsonl.

Usage:  python -m finrag.evaluation.lookup KO_2022 "total assets"
"""

import json
import sys
from pathlib import Path

import yaml


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit('usage: python -m finrag.evaluation.lookup KO_2022 "phrase"')
    doc_id, phrase = sys.argv[1], sys.argv[2].lower()
    parsed_dir = yaml.safe_load(Path("config.yaml").read_text())["corpus"]["parsed_dir"]
    path = Path(parsed_dir) / f"{doc_id}.jsonl"
    if not path.exists():
        raise SystemExit(f"{path} not found (doc ids look like KO_2022)")
    hits = 0
    for record in map(json.loads, path.open()):
        for line in record["text"].split("\n"):
            if phrase in line.lower():
                print(f"Item {record['item']:3} | {line[:220]}")
                hits += 1
    print(f"\n{hits} matching line(s)")


if __name__ == "__main__":
    main()