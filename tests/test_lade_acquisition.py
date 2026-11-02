import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("audit_lade", Path(__file__).resolve().parents[1] / "tools/audit_lade.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_bad_download_hash_never_creates_research_source(tmp_path, monkeypatch):
    content = b"bad source"
    metadata = [{"path": audit.FILENAME, "size": len(content), "lfs": {"oid": "0" * 64}}]
    monkeypatch.setattr(audit, "fetch", lambda url, maximum: json.dumps(metadata).encode() if "/tree/" in url else content)
    with pytest.raises(ValueError, match="hash mismatch"):
        audit.download(tmp_path)
    assert not (tmp_path / "delivery_cq.parquet").exists()


def test_existing_source_is_not_silently_replaced(tmp_path, monkeypatch):
    existing = b"unique research input"
    (tmp_path / "delivery_cq.parquet").write_bytes(existing)
    metadata = [{"path": audit.FILENAME, "size": 3, "lfs": {"oid": hashlib.sha256(b"new").hexdigest()}}]
    monkeypatch.setattr(audit, "fetch", lambda url, maximum: json.dumps(metadata).encode())
    with pytest.raises(ValueError, match="differs"):
        audit.download(tmp_path)
    assert (tmp_path / "delivery_cq.parquet").read_bytes() == existing
