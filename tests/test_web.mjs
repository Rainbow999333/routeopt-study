import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {verifyData, makeProjection, routeCoordinates, pathString} from "../web/model.mjs";

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
