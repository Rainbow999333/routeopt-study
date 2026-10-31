# Method / 方法

CVRP, one homogeneous fleet and depot. Every route starts and ends at D; sum of demand on a route must not exceed capacity. The number of nonempty routes cannot exceed max_vehicles. Every order appears exactly once. Minimize the sum of directed distance_m arcs. Empty instances use no vehicles and have zero distance; their improvement percentage is undefined.

NN chooses the nearest remaining capacity-feasible node with a return arc; ties are resolved by node ID. It closes the route when no node fits and starts another if vehicles remain. It is a heuristic, not a packing feasibility decision procedure.

2-opt reverses internal subsequences of one route at a time. It recomputes the entire directed route cost, skips unreachable moves and accepts only strict improvements. Demand and vehicle assignment remain unchanged. Search has time/pass bounds, and each result is validated independently.

Road matrix and geometry preparation happens before solving. Haversine does not supply road time. Static OSRM matrices are snapshots and do not model live traffic or all truck restrictions. Algorithms must share the same input and matrix hashes. Timing repeats retain the first solution rather than selecting a convenient best result.

Baseline and candidate must both be feasible before distance reduction is calculated. There is no default cost model or promised percentage improvement. Capacity unit is items, distance metres internally/km in reports, and optional travel time seconds. Coordinates are WGS84, serialized as [longitude, latitude] in GeoJSON.

Security: this is a bounded local experiment tool, not a public upload service. JSON inputs are capped at 16 MiB and 50 orders; invalid values/unsupported constraints are rejected. Public export needs human review; secrets, road matrices and arbitrary metadata are not copied. No shell evaluation of user data, external service calls or credentials are needed for demo.
