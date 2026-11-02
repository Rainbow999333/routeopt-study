# Dispatch interpretation

The website translates each verified baseline route into static driving durations using the **same original directed OSRM time matrix**, including the return to the depot. It reports both the sum of all vehicles' driving minutes and the longest individual route. These quantities have different meanings: saved vehicle-minutes are not equal to an earlier delivery or a shorter shift.

For the standard simulated-demand case, NN → 2-opt gives:

- Total vehicle driving minutes: 105.1367 → 98.8000.
- Longest route driving minutes: 57.5650 → 54.6017.
- Vehicles: 3 → 3. This comparison supplies no basis for reducing the fleet.

These are static `car.lua` model outputs, not observed truck/courier times. They omit parking, service, waiting and live traffic. Missing duration data remains missing; we do not infer it from kilometres or present a live ETA.

The editable variable-cost assumption uses:

`modeled difference per batch = (NN km − 2-opt km) × assumed currency per vehicle-km`

The default of 1 CNY/km is an illustrative sensitivity parameter, **not a company quote or a Chongqing market rate**. At that assumption the standard case differs by about 4.59 CNY per batch. Rates may be set to zero. Invalid, negative, nonfinite and excessively large inputs do not produce a normal estimate.

Fixed vehicle costs, salaried labour and implementation/maintenance costs are excluded. A difference in route kilometres does not prove reduced cash expenditure or justify workforce changes. No annual savings are extrapolated from one batch.

`routeopt.decision.decision_summary` revalidates saved experiment fingerprints, feasibility and metrics before deriving durations. The web builder adds this presentation evidence without changing saved solver records. Tests cover independent duration sums, missing times, tampered records, invalid assumptions, scenario changes and the distinction between total and longest duration.
