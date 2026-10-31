from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Any

SCHEMA_VERSION = "1.0"
MAX_ORDERS = 50


def fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def number(value: Any, name: str, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return float(value)


def identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise ValueError(f"{name} must be a nonempty string of at most 100 characters")
    return value


@dataclass(frozen=True)
class Stop:
    node_id: str
    lat: float
    lng: float
    demand: float = 0

    def __post_init__(self):
        identifier(self.node_id, "node_id")
        number(self.lat, "latitude", -90)
        number(self.lng, "longitude", -180)
        number(self.demand, "demand")
        if self.lat > 90 or self.lng > 180:
            raise ValueError("coordinates out of range")


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    depot: Stop
    orders: tuple[Stop, ...]
    max_vehicles: int
    capacity: float
    description: str = ""
    coordinate_system: str = "WGS84"
    demand_unit: str = "items"

    def __post_init__(self):
        identifier(self.scenario_id, "scenario_id")
        if self.coordinate_system != "WGS84" or self.demand_unit != "items":
            raise ValueError("v1 requires WGS84 coordinates and items as the demand unit")
        if isinstance(self.max_vehicles, bool) or not isinstance(self.max_vehicles, int):
            raise ValueError("max_vehicles must be an integer")
        if not 1 <= self.max_vehicles <= 50 or number(self.capacity, "capacity") <= 0:
            raise ValueError("vehicles must be 1..50 and capacity must be positive")
        if len(self.orders) > MAX_ORDERS:
            raise ValueError(f"at most {MAX_ORDERS} orders supported")
        ids = [s.node_id for s in self.stops]
        if len(ids) != len(set(ids)) or self.depot.demand != 0:
            raise ValueError("node IDs must be unique and depot demand must be zero")

    @property
    def stops(self) -> tuple[Stop, ...]:
        return (self.depot,) + self.orders

    def to_dict(self) -> dict:
        return {"schema_version": SCHEMA_VERSION, **asdict(self)}

    @property
    def digest(self) -> str:
        return fingerprint(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> Scenario:
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported scenario schema_version")
        # Explicitly reject unsupported constraints rather than silently ignoring them.
        allowed = {"schema_version", "scenario_id", "depot", "orders", "max_vehicles",
                   "capacity", "description", "coordinate_system", "demand_unit"}
        if set(data) - allowed:
            raise ValueError(f"unsupported scenario fields: {sorted(set(data) - allowed)}")
        return cls(scenario_id=data["scenario_id"], depot=Stop(**data["depot"]),
                   orders=tuple(Stop(**x) for x in data["orders"]),
                   max_vehicles=data["max_vehicles"], capacity=data["capacity"],
                   description=data.get("description", ""),
                   coordinate_system=data.get("coordinate_system", "WGS84"),
                   demand_unit=data.get("demand_unit", "items"))


@dataclass(frozen=True)
class Matrix:
    node_ids: tuple[str, ...]
    distances_m: tuple[tuple[float | None, ...], ...]
    provenance: dict
    durations_s: tuple[tuple[float | None, ...], ...] | None = None

    def __post_init__(self):
        n = len(self.node_ids)
        if not 1 <= n <= MAX_ORDERS + 1 or len(set(self.node_ids)) != n:
            raise ValueError("invalid matrix node IDs or size")
        for node_id in self.node_ids:
            identifier(node_id, "matrix node ID")
        for table in (self.distances_m, self.durations_s):
            if table is None:
                continue
            if len(table) != n or any(len(row) != n for row in table):
                raise ValueError("matrix must be square and match node IDs")
            for i, row in enumerate(table):
                for j, value in enumerate(row):
                    if value is not None:
                        number(value, "matrix value")
                    if i == j and value != 0:
                        raise ValueError("matrix diagonal must be zero")
        if self.durations_s is not None:
            for i in range(n):
                for j in range(n):
                    if (self.distances_m[i][j] is None) != (self.durations_s[i][j] is None):
                        raise ValueError("distance/time reachability must match")
        if not isinstance(self.provenance, dict) or not self.provenance.get("provider"):
            raise ValueError("matrix provenance needs a provider")

    def validate_for(self, scenario: Scenario):
        if self.node_ids != tuple(s.node_id for s in scenario.stops):
            raise ValueError("matrix node order does not match the scenario")
        coordinates = self.provenance.get("coordinates_sha256")
        if coordinates != coordinate_digest(scenario):
            raise ValueError("matrix coordinate fingerprint does not match the scenario")

    def to_dict(self) -> dict:
        return {"schema_version": SCHEMA_VERSION, **asdict(self)}

    @property
    def digest(self):
        return fingerprint(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> Matrix:
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported matrix schema_version")
        return cls(tuple(data["node_ids"]), tuple(tuple(r) for r in data["distances_m"]),
                   data["provenance"], None if data.get("durations_s") is None else
                   tuple(tuple(r) for r in data["durations_s"]))


def coordinate_digest(scenario: Scenario) -> str:
    return fingerprint({"coordinate_system": scenario.coordinate_system,
                        "nodes": [(s.node_id, s.lat, s.lng) for s in scenario.stops]})
