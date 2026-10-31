# Experiment records

chongqing-2026-11-01/ contains the four runs used to build the static website. Each result.json retains the scenario, exact matrix snapshot, software environment, input fingerprints, routes and independent feasibility results. comparison.md is derived, not hand-entered.

All point locations refer to public road nodes and all demand/fleet/depot purposes are simulated. These are not customer records or commercial dispatch data. Road matrices and applicable derived databases use ODbL-1.0; see data/chongqing/README.md.

The first result of each deterministic five-repeat batch is retained. Repetitions primarily measure timing variability. Matrix acquisition/preprocessing is excluded from reported solve time.

Optional OR-Tools records may use a separate Linux environment. Do not compare Windows/Linux wall-clock times as an algorithm benchmark without a controlled rerun. Current results do not certify operational feasibility or global optimality.
