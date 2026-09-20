# Round 48: management inference and complete provincial food audit

Status: **not accepted**. Round 47 remains the comparison baseline. The new
zero-reconstruction livelihood fallback is an experiment, not a production
assignment rule. No gameplay consumption, food-building supply or exports changed.

## What was verified

The completed canonical world run covers 20,929 locations. All 44 central regional
checks pass at the separate 100/200-year horizons, and every regional monthly
checkpoint replays exactly against the world run. This does not carry forward
round 47's broader 352 checks as evidence for changed inputs.

The new reusable management comparator verifies unchanged physical area, current
fields, water service, natural and infrastructure support, initial population by
type, building food and peasant employment. All named historical development
assignments remain unchanged. Its source hashes bind the paired artifacts.

The fallback applies to 3,367 locations, changing development in 3,362: 36 become
pastoral D18.75 and 3,326 become inferred foraging D6.25. Five already had the
selected value. Missing inputs are flagged separately; none were missing in this
run. Related reconstruction zeros remain uncertain evidence, not proof of absence.

The food auditor now supports `--all-provinces`. It reproduces the saved canonical
starting state and reconciles all 3,819 provincial budgets within 1e-8, including
production, consumption, subsistence surplus, non-peasant supply and recoverable
pressure consumption. Its regional failed-case list does not imply untested
provinces passed. Current cookery/victuals production is retained; hypothetical
future food buildings are not silently added to starting supply.

## Collateral failures

Locations ever experiencing unmet food increase from 5,058 to 5,082. At year 200,
340 locations have more cumulative unmet-food months. The 24 newly affected
locations belong to four provinces:

| Province | Locations | Unmet months per location by year 200 | Starting food balance |
|---|---:|---:|---:|
| Altayskoye | 6 | 701 | -1.2173 |
| Hazara | 8 | 2 | -2.0236 |
| Ifat | 5 | 10 | -10.7032 |
| Banaadir | 5 | 47 | -45.0870 |

These are cumulative monthly counts, not automatically consecutive starvation.
All four starting deficits disappear in the negligible-pressure diagnostic.
That diagnostic is not permission to fit their capacities to population.

In Altayskoye, only Onguday and Ust Koksa receive the new fallback. Their source
cropland and pasture are zero, while other locations in the same province have
recorded cultivated land and unchanged development. The shared provincial food
account transmits their increased pressure consumption to all six locations.
This is a concrete regression against treating reconstruction zeros as a
complete livelihood classification. No urban demand reduction follows from it.

Primary research provides an additional reason for caution: Zanina et al. (2021)
find combined pastoralism, small-scale cultivation and wild plant use in earlier
Altai archaeological populations. Its fifth-century BCE to fifth-century CE
coverage does **not** establish 1337 hectares or development. It supports rejecting
a confident foraging-only interpretation, not a numerical regional bonus.
Source: [author institution abstract](https://pure.qub.ac.uk/en/publications/plant-food-in-the-diet-of-the-early-iron-age-pastoralists-of-alta/),
[DOI](https://doi.org/10.1016/j.jasrep.2020.102740). Full text not inspected;
copyright Elsevier, no open redistribution license established.

## Decision and next requirement

Do not adopt the broad fallback on the strength of the 44 regional passes. A
potential crop class is insufficient historical evidence, but replacing it with
a foraging label from zero land reconstructions is also insufficient. Resolve
livelihood applicability and its uncertainty before assigning the management
advantage. Keep the separate 589 current-field/water-service conflicts open.

World population at 100/200 is 483.762m/521.819m versus 484.044m/522.126m in round
47. Small world differences do not excuse the local failures. No accepted model,
historical holdout, physical maximum or final full-suite claim is made here.

## Reproduction and tests

```sh
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_48.json --output artifacts/data/population_simulation/repair_round_48/world --scenario-file research/population_capacity/round_37_source_replay_scenario.json --override capacity.gaez_zero_development_fraction=4.5 --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/compare_management_candidate.py --before artifacts/data/population_simulation/repair_round_47/world --after artifacts/data/population_simulation/repair_round_48/world
uv run python research/population_capacity/audit_candidate_food_accounts.py --experiment artifacts/data/population_simulation/repair_round_48/world --all-provinces
uv run ppc test tests/test_historical_model.py tests/test_population_simulation_profile.py tests/test_simulation_fingerprints.py tests/test_crop_source_attribution.py -q
```

Focused regressions: **35 passed**. Paired assignments/checkpoints, new unmet-food
locations and input hashes are in `world/management_comparison`; the full food
ledger and reconciled budgets are in `world/world_food_audit`.
