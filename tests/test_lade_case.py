import copy
import importlib.util
from pathlib import Path

import pytest
from routeopt.io import read_json

spec = importlib.util.spec_from_file_location("run_lade_case", Path(__file__).resolve().parents[1] / "tools/run_lade_case.py")
case = importlib.util.module_from_spec(spec)
spec.loader.exec_module(case)


def records():
    return [dict(order_id=i, ds=501, region_id=1, courier_id=1, lat=29.5+i*.0001,
                 lng=106.5, accept_time="05-01 08:00:00", delivery_time="05-01 09:00:00") for i in range(21)]


def test_actual_package_counts_not_random_demand():
    stops = case.validate_records(records())
    assert len(stops) == 21 and sum(s.demand for s in stops) == 21


def test_same_position_parcels_aggregate_without_dropping_orders():
    rows = records()
    rows[-1]["lat"] = rows[0]["lat"]
    stops = case.validate_records(rows)
    assert len(stops) == 20 and sum(s.demand for s in stops) == 21
    assert stops[0].demand == 2


@pytest.mark.parametrize("invalid", ["duplicate", "different_courier", "future_task", "invalid_position"])
def test_source_group_cannot_be_silently_repaired(invalid):
    rows = records()
    if invalid == "duplicate": rows[-1]["order_id"] = rows[0]["order_id"]
    if invalid == "different_courier": rows[-1]["courier_id"] = 2
    if invalid == "future_task": rows[-1]["accept_time"] = "05-01 10:00:00"
    if invalid == "invalid_position": rows[-1]["lat"] = float("nan")
    original = copy.deepcopy(rows)
    with pytest.raises(ValueError): case.validate_records(rows)
    assert len(rows) == len(original)


@pytest.mark.parametrize("url", ["https://example.org", "http://127.0.0.1.evil.test", "http://name:secret@127.0.0.1:5000", "file:///tmp/a", "http://127.0.0.1:5000/?token=secret"])
def test_private_positions_only_sent_to_loopback(url):
    with pytest.raises(ValueError): case.loopback_base(url)
    assert case.loopback_base("http://127.0.0.1:5075/") == "http://127.0.0.1:5075"


def test_publication_whitelist_rejects_nested_private_fields_and_failed_road_gate():
    path = Path(__file__).resolve().parents[1] / "data/lade-study/public-summary.json"
    public = read_json(path)
    assert case.validate_public_summary(public) is public
    public["data_notice"]["order_id"] = "private"
    with pytest.raises(ValueError, match="private"):
        case.validate_public_summary(public)
    public = read_json(path)
    public["quality"]["max_snap_m_including_depot"] = 51
    with pytest.raises(ValueError, match="road gate"):
        case.validate_public_summary(public)
