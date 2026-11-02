export function verifyHistoricalStudy(value) {
  const allowed = new Set(["schema_version", "case_id", "study_type", "orders", "positions", "simulated_depots", "assumed_capacity_items", "assumed_max_vehicles", "matrix_sha256", "scenario_sha256", "source_repository", "source_revision", "source_sha256", "selected_source_sha256", "quality", "data_notice", "assumptions", "runs"]);
  if (!value || Object.keys(value).length !== allowed.size || Object.keys(value).some(k => !allowed.has(k)) || value.schema_version !== "1.0" || value.study_type !== "historical_tasks_counterfactual_routing") throw new Error("historical summary schema invalid");
  const privateKeys = new Set(["lat", "lng", "stops", "routes", "order_id", "courier_id", "region_id", "aoi_id", "accept_time", "delivery_time", "ds"]);
  function walk(item) { if (item && typeof item === "object") for (const [key, child] of Object.entries(item)) { if (privateKeys.has(key)) throw new Error("private historical fields"); walk(child); } }
  walk(value);
  if (!Number.isInteger(value.orders) || value.orders < 20 || value.orders > 500 || !Number.isInteger(value.positions) || value.positions < 20 || value.positions > 30 || value.orders < value.positions || value.simulated_depots !== 1) throw new Error("historical counts invalid");
  for (const name of ["matrix_sha256", "scenario_sha256", "source_sha256", "selected_source_sha256"]) if (!/^[a-f0-9]{64}$/.test(value[name])) throw new Error("historical fingerprint invalid");
  const q = value.quality;
  if (q?.threshold_m !== 50 || !Number.isFinite(q.max_snap_m_including_depot) || q.max_snap_m_including_depot < 0 || q.max_snap_m_including_depot > 50 || q.all_pairs_reachable !== true || q.selection_before_solving !== true || typeof q.coordinate_datum_confirmed !== "boolean" || !Number.isInteger(q.selected_after_quality_attempts) || q.selected_after_quality_attempts < 1) throw new Error("historical road gate failed");
  if (!Array.isArray(value.assumptions) || value.assumptions.length < 4 || value.assumptions.length > 12 || value.assumptions.some(s => typeof s !== "string" || s.length > 800)) throw new Error("historical assumptions missing");
  if (!Array.isArray(value.runs) || value.runs.length !== 3 || new Set(value.runs.map(r => r.solver)).size !== 3 || value.runs.some(r => !["nn", "2opt", "ortools"].includes(r.solver) || r.feasible !== true || !Number.isFinite(r.distance_km) || r.distance_km < 0 || !Number.isInteger(r.vehicles) || r.vehicles < 1 || [r.total_drive_minutes, r.longest_drive_minutes].some(t => t !== null && (!Number.isFinite(t) || t < 0)))) throw new Error("historical results invalid");
  const baseline = value.runs.find(r => r.solver === "nn").distance_km;
  if (!(baseline > 0) || value.runs.some(r => !Number.isFinite(r.improvement_pct) || Math.abs(r.improvement_pct - (baseline - r.distance_km) / baseline * 100) > 1e-6)) throw new Error("historical improvement invalid");
  return value;
}

export function dispatchComparison(scenario, rateText) {
  if (typeof rateText !== "string" || !rateText.trim() || rateText.length > 24) throw new Error("cost rate invalid");
  const rate = Number(rateText);
  if (!Number.isFinite(rate) || rate < 0 || rate > 100) throw new Error("cost rate invalid");
  const baseline = scenario.runs.find(r => r.solver === "nn");
  const candidate = scenario.runs.find(r => r.solver === "2opt");
  if (!baseline?.metrics.feasible || !candidate?.metrics.feasible) throw new Error("infeasible comparison");
  if (scenario.decision?.matrix_sha256 !== scenario.matrix_sha256) throw new Error("decision snapshot mismatch");
  const times = ["nn", "2opt"].map(solver => scenario.decision.runs[solver]);
  for (const time of times) {
    if (!time || [time.total_drive_minutes, time.longest_drive_minutes].some(v => v !== null && (!Number.isFinite(v) || v < 0))) throw new Error("invalid static times");
  }
  const distanceDifference = baseline.metrics.distance_km - candidate.metrics.distance_km;
  return {rate, distanceDifference, costDifference: distanceDifference * rate, times,
          baselineVehicles: baseline.metrics.vehicles_used, candidateVehicles: candidate.metrics.vehicles_used};
}

export function verifyData(bundle, geometry) {
  if (bundle?.schema_version !== "1.0" || geometry?.schema_version !== "1.0" ||
      !Array.isArray(bundle.scenarios) || !bundle.scenarios.length || bundle.scenarios.length > 10) {
    throw new Error("不支持的实验数据格式");
  }
  const keys = new Set();
  for (const scenario of bundle.scenarios) {
    if (keys.has(scenario.key) || scenario.data_mode !== "precomputed" ||
        scenario.matrix_sha256 !== geometry.matrix_sha256 || scenario.coordinate_system !== "WGS84" ||
        !Array.isArray(scenario.stops) || scenario.stops.length > 51) {
      throw new Error("实验与道路快照不一致");
    }
    keys.add(scenario.key);
    for (const stop of scenario.stops) {
      if (!Number.isFinite(stop.lat) || !Number.isFinite(stop.lng) ||
          Math.abs(stop.lat) > 90 || Math.abs(stop.lng) > 180 || !Number.isFinite(stop.demand)) {
        throw new Error("节点数据无效");
      }
    }
    for (const run of scenario.runs) {
      if (!["nn", "2opt", "ortools"].includes(run.solver)) throw new Error("未知算法");
      if (run.metrics.feasible) {
        if (!Number.isFinite(run.metrics.distance_km) || run.metrics.distance_km < 0) throw new Error("指标无效");
        for (const route of run.routes) for (let i = 1; i < route.length; i++) {
          const arc = geometry.arcs[route[i - 1] + ">" + route[i]];
          if (!arc || !Array.isArray(arc.coordinates) || arc.coordinates.length < 2 ||
              arc.coordinates.length > 20000) throw new Error("道路几何缺失");
          for (const p of arc.coordinates) {
            if (p.length !== 2 || !p.every(Number.isFinite) ||
                Math.abs(p[0]) > 180 || Math.abs(p[1]) > 90) throw new Error("道路坐标无效");
          }
        }
      }
    }
    if (!scenario.runs.some(r => r.solver === "nn") || !scenario.runs.some(r => r.solver === "2opt")) {
      throw new Error("缺少对照算法");
    }
  }
  return true;
}

export function routeCoordinates(route, geometry) {
  const coordinates = [];
  for (let i = 1; i < route.length; i++) {
    const arc = geometry.arcs[route[i - 1] + ">" + route[i]];
    if (!arc) throw new Error("路线缺少道路几何");
    coordinates.push(...arc.coordinates);
  }
  return coordinates;
}

export function makeProjection(points, width = 1000, height = 700, padding = 75) {
  if (!points.length) throw new Error("没有可投影的节点");
  const longitudeScale = Math.cos(points.reduce((sum, p) => sum + p[1], 0) / points.length * Math.PI / 180);
  const xs = points.map(p => p[0] * longitudeScale), ys = points.map(p => -p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min((width - 2 * padding) / Math.max(1e-6, maxX - minX),
                         (height - 2 * padding) / Math.max(1e-6, maxY - minY));
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  return ([lng, lat]) => [(lng * longitudeScale - cx) * scale + width / 2,
                         (-lat - cy) * scale + height / 2];
}

export function pathString(points, project) {
  return points.map((point, i) => {
    const p = project(point);
    return (i ? "L" : "M") + p[0].toFixed(2) + "," + p[1].toFixed(2);
  }).join("");
}
