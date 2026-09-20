# Round 49: Upper Nile extent audit and Fayyum canal management

Status: **candidate, not model acceptance**. This round starts from round 47 and
excludes round 48's rejected broad livelihood fallback. Shared coefficients,
consumption and food-building supply remain unchanged.

## Physical evidence and geography

The cached Borsch (2000) article explicitly uses two million modern feddans of
4,200 m² for a rough 1315 Upper Egyptian basin-area computation: **8,400 km²**.
Its one-metre depth calculation implies 8.4 billion m³; that is dimensional
consistency, not independent water-volume validation. The article is CC-BY-4.0.

The new physical audit reads no population data. It records every location in
four valley provinces and a deliberately broad northern bracket including all
Cairo province. Current fields total 3,004.15 km² in the core and 5,482.75 km²
including all Cairo; water-served fields total 2,644.59 and 4,875.33 km². Both
brackets are below the rough historical basin estimate. This exposes a remaining
extent discrepancy even though the regional food screens pass.

These are province brackets, not historical floodplain polygons. Cairo includes
Delta land, and Bahnasa includes Faiyum's distinct canal system. The audit lists
that exception separately. It does not allocate hectares, create a confidence
interval absent from the source, or certify the final Nile geometry gate.

## A specific assignment omission corrected

Faiyum has `has_river=false`, so the general Nile hydraulic assessment excludes
it. The resulting generic analogue gives D18.75 despite documented maintained
canal agriculture. The scholarly [Fayyum survey project](https://projects.history.qmul.ac.uk/ruralsocietyislam/database/i-1-the-village/)
describes gravity-fed canals, weirs and village water allocations. Its
[historical map documentation](https://projects.history.qmul.ac.uk/ruralsocietyislam/map/)
also makes the changing lake boundary and mixed mapping sources explicit.

The named assignment uses the existing Egyptian hydraulic-management bounds
(D55–85 and water coverage 0.8–1.0). These are inferred comparable-system game
parameters, not measured medieval percentages. The canal mechanism is recorded
separately from seasonal basin irrigation. Continuity from the 1243–45 survey to
1337 is an explicit pre-plague assumption. No extra crop cycle, new cultivated
hectares, building supply or population-derived adjustment is introduced.

The evidence document and both cached source pages are hash-pinned in
`historical_assignments_round_49.json`.

## Isolated results

All other starting locations remain unchanged. Faiyum keeps 188.22045 km² of
fields. Its central water-served extent changes from 110.25193 to 169.39840 km²;
development changes from 18.75 to 70. Total capacity changes from 65.642k to
233.569k, through the canonical direct-infrastructure and relative-factor formula.
These are candidate values, not accepted building targets.

The complete four-location Bahnasa food-sharing province passes all eight
unchanged/low/central/high horizon screens:

| Scenario | Population / initial, year 100 | Year 200 | Unmet food after startup |
|---|---:|---:|---:|
| Unchanged | 1.975 | 2.114 | 0 |
| Low | 2.402 | 2.955 | 0 |
| Central | 2.434 | 3.084 | 0 |
| High | 2.456 | 3.153 | 0 |

Every scenario also passes the per-location development and early-drawdown
screens. These results demonstrate survival and pressure response, not a frozen
historical demographic growth benchmark. The increase in long-run growth remains
visible for demographic and sensitivity evaluation.

Starting provincial production remains **505.1326 food/month**. Central
consumption falls from 236.3897 to 223.9843; surplus rises from 268.7429 to
281.1483. The food auditor reproduces the canonical state and provincial account.
Urban food-building supply and all population-type consumption rates stay fixed.

## Global comparison and verification

The complete world run retains all44 central regional horizon checks. The new
isolated-world audit verifies exact equality of every saved checkpoint column
outside Bahnasa province at years0/25/100/200. No location gains additional
unmet-food months. World population reaches484.154m/522.358m at100/200; world
totals are diagnostics, not historical acceptance targets. The existing5,058
locations with unmet food remain unresolved. This correction does not purport
to repair the broader water-source gaps or unsupported management analogues.

Canonical candidate point maps and provincial outcome plots were regenerated;
the capacity/development/infrastructure/opportunity map was visually inspected.
The renderer now accepts either the broad acceptance runner's horizon table or
the world runner's evaluated viability table with an explicit scenario.

`uv run ppc test -q`: **867 passed,1 skipped**,583.81seconds. A focused rerun with
`-rs` confirms the skip: current local `error.log` has no setup-building errors
(`tests/test_setup_building_corrections.py:221`). Subsequent research audit and
rendering scripts were executed against their actual artifacts; no gameplay core
changed after the full suite. No game export or live deployment occurred.

## Reproduction

All outputs below are under `artifacts/data/population_simulation/repair_round_49`.

```sh
uv run python research/population_capacity/audit_upper_egypt_extent.py --ledger artifacts/data/population_simulation/repair_round_47/world/starting_ledger.parquet --output artifacts/data/population_simulation/repair_round_49/upper_egypt_extent
uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_49.json --system fayyum_maintained_canal_agriculture --output artifacts/data/population_simulation/repair_round_49/fayyum_management --scenario-file research/population_capacity/round_37_source_replay_scenario.json --scenario common_slower_quarter --override capacity.gaez_zero_development_fraction=4.5 --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/audit_management_food_accounts.py --experiment artifacts/data/population_simulation/repair_round_49/fayyum_management --candidate central
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_49.json --output artifacts/data/population_simulation/repair_round_49/world --scenario-file research/population_capacity/round_37_source_replay_scenario.json --override capacity.gaez_zero_development_fraction=4.5 --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/audit_isolated_world_change.py --before artifacts/data/population_simulation/repair_round_47/world --after artifacts/data/population_simulation/repair_round_49/world --tag faiyum
uv run python research/population_capacity/render_acceptance_round_25.py --output artifacts/data/population_simulation/repair_round_49/world --scenario common_slower_quarter
```

The remaining historical extent, livelihood evidence, independent holdout,
complete scenario, demographic and physical-opportunity gates are unchanged.
Neither source presence nor a passing regional survival test closes them.
