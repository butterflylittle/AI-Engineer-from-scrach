import json
from pathlib import Path


def reciprocal_rank(returned_ids: list[str], expected_ids: list[str]) -> float:
    expected = set(expected_ids)
    return next((1 / rank for rank, item in enumerate(returned_ids, 1) if item in expected), 0.0)


if __name__ == "__main__":
    rows = [json.loads(line) for line in Path(__file__).with_name("golden.jsonl").read_text().splitlines()]
    print(f"Loaded {len(rows)} golden examples. Feed retrieval results into reciprocal_rank().")
