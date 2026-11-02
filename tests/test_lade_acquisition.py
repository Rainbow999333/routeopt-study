import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("audit_lade", Path(__file__).resolve().parents[1] / "tools/audit_lade.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.fixture
def available_disk(monkeypatch):
    monkeypatch.setattr(audit.shutil, "disk_usage", lambda path: SimpleNamespace(total=10*1024**3, used=2*1024**3, free=8*1024**3))


def test_bad_download_hash_never_creates_research_source(tmp_path, monkeypatch, available_disk):
    content = b"bad source"
    metadata = [{"path": audit.FILENAME, "size": len(content), "lfs": {"oid": "0" * 64}}]
    monkeypatch.setattr(audit, "fetch", lambda url, maximum: json.dumps(metadata).encode() if "/tree/" in url else content)
    with pytest.raises(ValueError, match="hash mismatch"):
        audit.download(tmp_path)
    assert not (tmp_path / "delivery_cq.parquet").exists()


def test_existing_source_is_not_silently_replaced(tmp_path, monkeypatch, available_disk):
    existing = b"unique research input"
    (tmp_path / "delivery_cq.parquet").write_bytes(existing)
    metadata = [{"path": audit.FILENAME, "size": 3, "lfs": {"oid": hashlib.sha256(b"new").hexdigest()}}]
    monkeypatch.setattr(audit, "fetch", lambda url, maximum: json.dumps(metadata).encode())
    with pytest.raises(ValueError, match="differs"):
        audit.download(tmp_path)
    assert (tmp_path / "delivery_cq.parquet").read_bytes() == existing


@pytest.mark.parametrize("used,free", [(8*1024**3, 2*1024**3), (1024**3, 512*1024**2)])
def test_disk_gate_blocks_before_network_or_source_write(tmp_path, monkeypatch, used, free):
    monkeypatch.setattr(audit.shutil, "disk_usage", lambda path: SimpleNamespace(total=10*1024**3, used=used, free=free))
    def unexpected_fetch(*args):
        pytest.fail("disk rejection must precede network access")
    monkeypatch.setattr(audit, "fetch", unexpected_fetch)
    with pytest.raises(RuntimeError, match="research disk"):
        audit.download(tmp_path)
    assert not (tmp_path / "delivery_cq.parquet").exists()
