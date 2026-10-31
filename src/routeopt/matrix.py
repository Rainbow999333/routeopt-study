"""Matrix providers. Loaded snapshots keep experiments independent of the network."""
from datetime import datetime, timezone
import math

from .models import Matrix, Scenario, coordinate_digest


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(
        math.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(min(1, max(0, a))))


def haversine_matrix(scenario: Scenario) -> Matrix:
    return Matrix(tuple(s.node_id for s in scenario.stops), tuple(
        tuple(haversine_m(a.lat, a.lng, b.lat, b.lng) for b in scenario.stops)
        for a in scenario.stops), {
            "provider": "haversine",
            "provider_version": "mean-earth-radius-6371008.8",
            "distance_unit": "m", "duration_unit": None,
            "coordinate_system": "WGS84",
            "coordinates_sha256": coordinate_digest(scenario),
            "traffic_mode": "straight_line",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "limitations": "Spherical approximation; not driving distance or travel time.",
            "license": "Synthetic sample coordinates; no third-party road data.",
        })
