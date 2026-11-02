import {verifyData, routeCoordinates, makeProjection, pathString, dispatchComparison, verifyHistoricalStudy} from "./model.mjs";

const $ = id => document.getElementById(id);
const ns = "http://www.w3.org/2000/svg";
const colors = ["#176854", "#355f8c", "#a2542e", "#775c8b", "#72681f", "#335b62"];
const state = {bundle: null, geometry: null, roads: null, scenario: null, view: "both",
               selectedRoute: null, zoom: 1, playing: false, progress: 0, frame: null};
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
let project;

function svg(name, attributes = {}) {
  const element = document.createElementNS(ns, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}
function metric(value, digits = 2) {
  return value == null ? "未测" : Number(value).toFixed(digits);
}
function setNumber(id, number, unit) {
  const target = $(id);
  target.replaceChildren(document.createTextNode(number), Object.assign(document.createElement("small"), {textContent: unit}));
}
function label(solver) { return ({nn: "最近邻 NN", "2opt": "NN + 2-opt", ortools: "OR-Tools"})[solver]; }
function run(solver) { return state.scenario.runs.find(value => value.solver === solver); }
function stopPlayback(reset = false) {
  state.playing = false;
  cancelAnimationFrame(state.frame);
  state.frame = null;
  if (reset) { state.progress = 0; $("playback-markers").replaceChildren(); }
  $("play").textContent = reducedMotion.matches ? "已减少动态" : (state.progress ? "▷ 继续播放" : "▷ 播放路线");
  $("play").disabled = reducedMotion.matches || !state.scenario;
}

function drawRoutes() {
  $("baseline-routes").replaceChildren();
  $("optimized-routes").replaceChildren();
  for (const solver of ["nn", "2opt"]) {
    const result = run(solver);
    const group = $(solver === "nn" ? "baseline-routes" : "optimized-routes");
    group.hidden = false; // SVG visibility is controlled explicitly below.
    group.style.display = state.view !== "both" && state.view !== solver ? "none" : "";
    if (!result?.metrics.feasible) continue;
    result.routes.forEach((route, index) => {
      const path = svg("path", {d: pathString(routeCoordinates(route, state.geometry), project),
                               "data-vehicle": index, "data-solver": solver});
      path.style.stroke = solver === "nn" && state.view === "both" ? "#b84b2d" : colors[index % colors.length];
      if (state.selectedRoute !== null && state.selectedRoute !== index) path.style.opacity = ".12";
      const title = svg("title"); title.textContent = label(solver) + " · 车辆 " + (index + 1); path.append(title);
      group.append(path);
    });
  }
}
function drawStops() {
  const group = $("stop-markers"); group.replaceChildren();
  for (const stop of state.scenario.stops) {
    const [x, y] = project([stop.lng, stop.lat]);
    const marker = stop.is_depot
      ? svg("rect", {x: x - 9, y: y - 9, width: 18, height: 18, rx: 2, class: "depot-marker"})
      : svg("circle", {cx: x, cy: y, r: 4.5, class: "stop-circle"});
    const text = stop.is_depot ? "模拟仓库 D" : stop.node_id + " · 模拟需求 " + stop.demand + " 件";
    marker.setAttribute("tabindex", "0"); marker.setAttribute("role", "img"); marker.setAttribute("aria-label", text);
    const title = svg("title"); title.textContent = text; marker.append(title);
    marker.addEventListener("focus", () => $("stop-info").textContent = text);
    marker.addEventListener("mouseenter", () => $("stop-info").textContent = text);
    group.append(marker);
    if (stop.is_depot) {
      const textElement = svg("text", {x, y: y + 4, fill: "#fffefa", "text-anchor": "middle",
                                      "font-size": 11, "pointer-events": "none"});
      textElement.textContent = "仓"; group.append(textElement);
    }
  }
}
function renderTable() {
  const tbody = $("comparison-body"); tbody.replaceChildren();
  for (const result of state.scenario.runs) {
    const m = result.metrics;
    const row = document.createElement("tr");
    if (result.solver === "2opt") row.className = "optimized";
    const ms = m.solver_elapsed_s * 1000;
    for (const value of [label(result.solver), metric(m.distance_km, 3),
                         m.vehicles_used ?? "—", m.feasible ? metric(m.average_load_pct, 1) + "%" : "—",
                         result.status === "skipped" ? "未安装" : (ms < 1 ? "< 1 ms" : metric(ms, 1) + " ms"),
                         m.feasible ? "通过" : (result.status === "skipped" ? "跳过" : "未通过")]) {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    }
    tbody.append(row);
  }
}
function renderRouteList() {
  const result = run(state.view === "nn" ? "nn" : "2opt");
  $("route-list-title").textContent = state.view === "nn" ? "最近邻车辆路线" : "2-opt 车辆路线";
  const list = $("route-list"); list.replaceChildren();
  const demands = new Map(state.scenario.stops.map(stop => [stop.node_id, stop.demand]));
  result.routes.forEach((route, index) => {
    const button = document.createElement("button");
    button.className = "route-button"; button.style.setProperty("--route-color", colors[index % colors.length]);
    button.setAttribute("aria-pressed", String(state.selectedRoute === index));
    const swatch = document.createElement("i"); swatch.setAttribute("aria-hidden", "true");
    const title = document.createElement("span"); title.textContent = "车辆 " + String(index + 1).padStart(2, "0");
    const detail = document.createElement("span");
    detail.textContent = (route.length - 2) + " 点 · " + route.reduce((sum, n) => sum + demands.get(n), 0) + " 件";
    button.append(swatch, title, detail);
    button.addEventListener("click", () => {
      state.selectedRoute = state.selectedRoute === index ? null : index;
      stopPlayback(true); drawRoutes(); renderRouteList();
    });
    list.append(button);
  });
}
function renderDecision() {
  if (!state.scenario) return;
  try {
    const comparison = dispatchComparison(state.scenario, $("cost-rate").value);
    $("cost-error").hidden = true; $("cost-rate").setAttribute("aria-invalid", "false");
    const duration = field => comparison.times.map(t => t[field] === null ? "未提供" : metric(t[field], 2)).join(" → ");
    $("drive-total").textContent = duration("total_drive_minutes") + " 车分钟";
    $("drive-longest").textContent = duration("longest_drive_minutes") + " 分钟";
    const difference = comparison.costDifference;
    $("cost-estimate").textContent = "按该假设，每批里程变动费用" + (difference >= 0 ? "减少 " : "增加 ") + metric(Math.abs(difference), 2) + " 元（NN → 2-opt）。";
    $("dispatch-implication").textContent = "本场景用车 " + comparison.baselineVehicles + " → " + comparison.candidateVehicles +
      " 辆。" + (comparison.baselineVehicles === comparison.candidateVehicles ? "可讨论访问顺序调整；没有减车依据。" : "车辆变化仍须结合实际服务要求核验。") + "固定月薪和车辆费用不随里程自动下降。";
  } catch {
    $("drive-total").textContent = "—"; $("drive-longest").textContent = "—";
    $("dispatch-implication").textContent = "";
    $("cost-error").hidden = false; $("cost-rate").setAttribute("aria-invalid", "true");
    $("cost-estimate").textContent = "当前不能计算费用差；请核对输入及实验数据。";
  }
}

function renderScenario() {
  stopPlayback(true); state.selectedRoute = null;
  const scenario = state.scenario, baseline = run("nn"), candidate = run("2opt"), m = candidate.metrics;
  $("scenario-help").textContent = scenario.title + " · " + scenario.orders_count +
    " 个配送点 · 最多 " + scenario.max_vehicles + " 辆车 · 容量 " + scenario.capacity +
    " 件/辆 · 总需求 " + scenario.total_demand + " 件 · 同一矩阵快照";
  setNumber("distance", metric(m.distance_km, 3), "km");
  $("distance-change").textContent = baseline.metrics.feasible && m.feasible
    ? "比最近邻减少 " + metric(baseline.metrics.distance_km - m.distance_km, 3) + " km（" +
       metric(candidate.improvement_pct, 2) + "%）" : "该场景未得到可对比的可行方案";
  $("vehicles").textContent = (m.vehicles_used ?? "—") + " 辆";
  $("load").textContent = metric(m.average_load_pct, 1) + "%";
  $("capacity").textContent = scenario.capacity + " 件";
  $("demand").textContent = scenario.total_demand + " 件";
  $("feasibility").textContent = m.feasible ? "✓ 无漏单、重复、超载或不可达路段" : "本场景未通过可行性校验";
  $("matrix-hash").textContent = scenario.matrix_sha256;
  $("map-description").textContent = scenario.title + "。重庆南岸 " + scenario.orders_count +
    " 个公共道路节点上的模拟配送，地图显示真实道路折线。详细指标见下方表格。";
  drawRoutes(); drawStops(); renderTable(); renderRouteList(); updateZoom();
  renderDecision();
  $("stop-info").textContent = "圆点为模拟配送位置，方块为模拟仓库。";
}
function updateZoom() {
  $("map-content").setAttribute("transform", "translate(500 350) scale(" + state.zoom + ") translate(-500 -350)");
  $("zoom-in").disabled = state.zoom >= 2.5;
  $("zoom-out").disabled = state.zoom <= .75;
}
function playback() {
  if (state.playing) { stopPlayback(); return; }
  if (reducedMotion.matches) return;
  const group = $(state.view === "nn" ? "baseline-routes" : "optimized-routes");
  const paths = [...group.querySelectorAll("path")].filter(path =>
    state.selectedRoute === null || Number(path.dataset.vehicle) === state.selectedRoute);
  if (!paths.length) return;
  $("playback-markers").replaceChildren();
  const dots = paths.map(path => {
    const dot = svg("circle", {r: 6.5, fill: colors[Number(path.dataset.vehicle) % colors.length],
                               class: "playback-dot"});
    $("playback-markers").append(dot);
    return {path, dot, length: path.getTotalLength()};
  });
  if (state.progress >= 1) state.progress = 0;
  state.playing = true; $("play").textContent = "Ⅱ 暂停播放";
  const start = performance.now() - state.progress * 12000;
  function tick(now) {
    state.progress = Math.min(1, (now - start) / 12000);
    for (const {path, dot, length} of dots) {
      const point = path.getPointAtLength(length * state.progress);
      dot.setAttribute("cx", point.x); dot.setAttribute("cy", point.y);
    }
    if (state.progress < 1 && state.playing) state.frame = requestAnimationFrame(tick);
    else { stopPlayback(); $("play").textContent = "↻ 再次播放"; }
  }
  state.frame = requestAnimationFrame(tick);
}

async function getData(filename, maxBytes) {
  const response = await fetch("./data/" + filename);
  if (!response.ok) throw new Error("实验文件未能读取");
  const text = await response.text();
  if (text.length > maxBytes) throw new Error("实验文件过大");
  return JSON.parse(text);
}
async function boot() {
  try {
    const [bundle, geometry, roads] = await Promise.all([
      getData("scenarios.json", 1024 * 1024), getData("geometry.json", 2 * 1024 * 1024),
      getData("roads.json", 2 * 1024 * 1024)]);
    verifyData(bundle, geometry);
    if (!Array.isArray(roads.roads) || roads.roads.length > 10000) throw new Error("道路背景无效");
    state.bundle = bundle; state.geometry = geometry; state.roads = roads;
    const coordinates = Object.values(geometry.arcs).flatMap(arc => arc.coordinates);
    project = makeProjection(coordinates);
    $("base-roads").setAttribute("d", roads.roads.map(road => pathString(road, project)).join(""));
    const select = $("scenario-select"); select.replaceChildren();
    for (const scenario of bundle.scenarios) {
      const option = document.createElement("option"); option.value = scenario.key; option.textContent = scenario.title;
      select.append(option);
    }
    state.scenario = bundle.scenarios[0];
    const standard = state.scenario.runs.find(r => r.solver === "2opt");
    setNumber("hero-improvement", metric(standard.improvement_pct), "%");
    setNumber("hero-vehicles", String(standard.metrics.vehicles_used), "辆");
    select.disabled = false; $("view-switch").disabled = false;
    select.addEventListener("change", () => {
      state.scenario = bundle.scenarios.find(scenario => scenario.key === select.value);
      renderScenario();
    });
    document.querySelectorAll('input[name="view"]').forEach(input => input.addEventListener("change", () => {
      state.view = input.value; state.selectedRoute = null; stopPlayback(true); drawRoutes(); renderRouteList();
    }));
    $("play").addEventListener("click", playback);
    $("show-all").addEventListener("click", () => {
      state.selectedRoute = null; stopPlayback(true); drawRoutes(); renderRouteList();
    });
    $("zoom-in").addEventListener("click", () => {state.zoom = Math.min(2.5, state.zoom + .25); updateZoom();});
    $("zoom-out").addEventListener("click", () => {state.zoom = Math.max(.75, state.zoom - .25); updateZoom();});
    $("zoom-reset").addEventListener("click", () => {state.zoom = 1; updateZoom();});
    $("cost-rate").addEventListener("input", renderDecision);
    reducedMotion.addEventListener("change", () => stopPlayback(true));
    document.addEventListener("visibilitychange", () => {if (document.hidden) stopPlayback();});
    renderScenario();
  } catch (error) {
    $("load-error").hidden = false;
    $("scenario-help").textContent = "数据加载未完成；请检查静态资源是否一并发布。";
    $("scenario-select").disabled = true; $("view-switch").disabled = true;
    $("play").disabled = true;
    console.error("Routeopt data initialization failed:", error.message);
  }
}
async function bootHistory() {
  try {
    const history = verifyHistoricalStudy(await getData("history.json", 128 * 1024));
    $("history-quality").textContent = history.orders + " 条包裹记录 · " + history.positions + " 个脱敏位置 · " + history.simulated_depots + " 个模拟起终点 · 假设最多 " + history.assumed_max_vehicles + " 辆车、容量 " + history.assumed_capacity_items + " 件/辆。顺序检查 " + history.quality.selected_after_quality_attempts + " 个完整批次后选中；本组最大吸附 " + metric(history.quality.max_snap_m_including_depot, 2) + " 米，全点对可达。";
    $("history-body").replaceChildren();
    for (const run of history.runs) {
      const row = document.createElement("tr");
      for (const text of [label(run.solver), metric(run.distance_km, 3), run.total_drive_minutes === null ? "未提供" : metric(run.total_drive_minutes, 2), String(run.vehicles), run.solver === "nn" ? "基准" : metric(run.improvement_pct, 2) + "%"]) {
        const cell = document.createElement("td"); cell.textContent = text; row.append(cell);
      }
      $("history-body").append(row);
    }
    $("history-assumptions").replaceChildren();
    for (const text of history.assumptions) { const li = document.createElement("li"); li.textContent = text; $("history-assumptions").append(li); }
    $("history-status").hidden = true; $("history-content").hidden = false;
  } catch {
    $("history-content").hidden = true;
    $("history-status").textContent = "独立历史案例暂时未能加载；上方24点模拟实验仍可使用。";
  }
}
boot();
bootHistory();
