import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {verifyData, makeProjection, routeCoordinates, pathString, dispatchComparison} from "../web/model.mjs";

const data = name => JSON.parse(readFileSync(new URL("../web/data/" + name, import.meta.url)));

test("published scenarios and road geometry share fingerprints and complete route arcs", () => {
  const bundle = data("scenarios.json"), geometry = data("geometry.json");
  assert.equal(verifyData(bundle, geometry), true);
  assert.equal(bundle.scenarios.length, 4);
  assert.equal(bundle.scenarios[0].orders_count, 24);
  for (const scenario of bundle.scenarios) {
    for (const run of scenario.runs) {
      assert.equal(run.metrics.feasible, true);
      for (const route of run.routes) assert.ok(routeCoordinates(route, geometry).length > 2);
    }
  }
});

test("reject a stale geometry snapshot", () => {
  const geometry = data("geometry.json"); geometry.matrix_sha256 = "stale";
  assert.throws(() => verifyData(data("scenarios.json"), geometry), /快照/);
});

test("cost assumptions do not imply fewer vehicles or cash wage savings", () => {
  const scenario = data("scenarios.json").scenarios[0];
  const comparison = dispatchComparison(scenario, "1.5");
  assert.ok(Math.abs(comparison.costDifference - 6.88395) < 0.0001);
  assert.equal(comparison.baselineVehicles, 3);
  assert.equal(comparison.candidateVehicles, 3);
  assert.equal(dispatchComparison(scenario, "0").costDifference, 0);
  assert.ok(Math.abs(comparison.times[0].total_drive_minutes - 105.13666667) < 1e-6);
  assert.ok(Math.abs(comparison.times[1].longest_drive_minutes - 54.60166667) < 1e-6);
});

test("reject invalid rates, stale decision evidence and nonfinite times", () => {
  const scenario = data("scenarios.json").scenarios[0];
  for (const rate of ["", " ", "NaN", "Infinity", "-1", "101", "1".repeat(25)]) assert.throws(() => dispatchComparison(scenario, rate));
  scenario.decision.matrix_sha256 = "stale";
  assert.throws(() => dispatchComparison(scenario, "1"), /snapshot/);
  scenario.decision.matrix_sha256 = scenario.matrix_sha256;
  scenario.decision.runs.nn.total_drive_minutes = Infinity;
  assert.throws(() => dispatchComparison(scenario, "1"), /static times/);
});

test("reject missing arcs instead of rendering a fake straight-line road", () => {
  assert.throws(() => routeCoordinates(["D", "A"], {arcs: {}}), /缺少/);
});

test("projection retains geographic orientation and handles a single location", () => {
  const project = makeProjection([[106, 29], [106.1, 29.1]]);
  const a = project([106, 29]), b = project([106.1, 29.1]);
  assert.ok(a[0] < b[0] && a[1] > b[1]);
  assert.deepEqual(makeProjection([[106, 29]])([106, 29]), [500, 350]);
  assert.ok(!pathString([[106, 29], [106.1, 29.1]], project).includes("NaN"));
});
