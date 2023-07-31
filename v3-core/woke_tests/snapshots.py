import json
from pathlib import Path


def match_snapshot(value, file_path, ident):
    filename = Path(__file__).parent / "__snapshots__" / f"{Path(file_path).name}.snap"
    with open(filename, "r") as f:
        expected = json.load(f)
        assert value == int(expected[ident])
