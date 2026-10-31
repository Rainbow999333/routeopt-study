"""Rebuild public data from committed experiment records and compare every byte."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    scratch = root / "out"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="web-rebuild-", dir=scratch) as directory:
        output = Path(directory) / "data"
        environment = {**os.environ, "PYTHONPATH": str(root / "src")}
        subprocess.run([sys.executable, str(root / "tools/build_web.py"), "--out", str(output)],
                       cwd=root, env=environment, check=True, capture_output=True, text=True)
        expected = root / "web/data"
        actual_names = sorted(p.name for p in output.iterdir())
        expected_names = sorted(p.name for p in expected.iterdir())
        if actual_names != expected_names:
            raise ValueError("public data file set differs from the committed experiment build")
        evidence = {}
        for name in actual_names:
            actual, saved = (output / name).read_bytes(), (expected / name).read_bytes()
            if actual != saved:
                raise ValueError(f"stale or modified public data: {name}")
            evidence[name] = {"bytes": len(actual), "sha256": hashlib.sha256(actual).hexdigest()}
        print(json.dumps({"reproducible": True, "files": evidence}))


if __name__ == "__main__":
    main()
