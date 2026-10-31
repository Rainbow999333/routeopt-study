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
