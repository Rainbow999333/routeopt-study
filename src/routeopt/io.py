import json
from pathlib import Path

MAX_FILE_BYTES = 16 * 1024 * 1024


def read_json(path: str | Path) -> dict:
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("input file exceeds 16 MiB")
    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    with path.open(encoding="utf-8") as stream:
        result = json.load(stream, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("expected a JSON object")
    return result


def write_json(path: str | Path, value: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
