import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("fetch_overpass",
    Path(__file__).resolve().parents[1] / "tools" / "fetch_overpass.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


@pytest.mark.parametrize("bbox", [(0, 0, 1, 1), (2, 1, 1, 2), (0, 0, float("nan"), 1)])
def test_bounded_extract(bbox):
    with pytest.raises(ValueError):
        fetch.build_query(bbox)


def test_query_requests_restrictions_and_nodes():
    query = fetch.build_query((29.49, 106.535, 29.56, 106.625))
    assert "restriction" in query and "out body" in query and "[timeout:60]" in query
