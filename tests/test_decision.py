import copy
from pathlib import Path

import pytest

from routeopt.decision import decision_summary
from routeopt.experiment import compare
from routeopt.io import read_json
from routeopt.matrix import haversine_matrix
from routeopt.models import Scenario, Stop


def test_saved_directed_duration_recalculation_and_vehicle_semantics():
    record = read_json(Path(__file__).resolve().parents[1] / "experiments/chongqing-2026-11-01/standard/result.json")
    original = copy.deepcopy(record)
    summary = decision_summary(record)
    nn, opt = (summary["runs"][s] for s in ("nn", "2opt"))
    assert nn["total_drive_minutes"] == pytest.approx(105.13666666666667)
    assert opt["total_drive_minutes"] == pytest.approx(98.8)
    assert nn["longest_drive_minutes"] == pytest.approx(57.565)
    assert opt["longest_drive_minutes"] == pytest.approx(54.60166666666667)
    assert nn["total_drive_minutes"] - opt["total_drive_minutes"] != pytest.approx(nn["longest_drive_minutes"] - opt["longest_drive_minutes"])
    assert nn["vehicles"] == opt["vehicles"] == 3
    assert record == original


def test_no_durations_does_not_infer_time_from_distance():
    s = Scenario("no-time", Stop("D", 0, 0), (Stop("A", 0, .01, 1),), 1, 1)
    summary = decision_summary(compare(s, haversine_matrix(s)))
    assert summary["runs"]["nn"]["total_drive_minutes"] is None
    assert summary["runs"]["2opt"]["longest_drive_minutes"] is None


def test_tampered_input_rejected_before_deriving_business_claims():
    record = read_json(Path(__file__).resolve().parents[1] / "experiments/chongqing-2026-11-01/standard/result.json")
    record["matrix"]["durations_s"][0][1] += 100
    with pytest.raises(ValueError, match="fingerprint"):
        decision_summary(record)
