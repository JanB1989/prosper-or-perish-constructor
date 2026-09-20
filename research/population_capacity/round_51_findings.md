# Round 51: bounded Upper Nile area allocation and simulation

Status: **exploratory spatial sensitivity; not adopted**. Round49 remains the
working comparison candidate. A sourced regional total does not determine its
local distribution, and survival alone cannot select that distribution.

## Implemented mechanism

The canonical `allocate_regional_fields` function distributes additional fields
by explicit land-evidence weights, conserves current fields, and saturates at
remaining convertible land. Zero-weight locations receive no inferred expansion.
Impossible totals, missing evidence and duplicate locations fail explicitly.
Population is not read by the experiment builder or allocator.

The frozen contract uses Borsch's rough8,400km² Upper Egyptian basin estimate.
Three nested scopes cover the valley provinces excluding Faiyum, then add
Atfih/Giza, then Cairo. Qalyub/Menouf in the Delta remain excluded. Each is tested
with HYDE1300 and LUH2-derived1300 cultivated-land weights. These weights are
related evidence, not independent source holdouts. The scopes are inferred game
crosswalks, not historical floodplain polygons.

Each generated assignment uses the same existing hydraulic-management range and
native capacity formula. Newly assigned fields displace livelihoods and consume
remaining land opportunity through the canonical historical model. The source
total is imposed by construction; it is not subsequently counted as an
independently passed validation benchmark. Operational water coverage remains
0.8–1.0, giving7,560km² served at the central0.9 value, distinct from gross basins.

## Results and accounting

All six experiments pass52 horizon screens each across26 complete provinces:
**312/312**. The extended reusable runner includes the four Upper Nile provinces
alongside the original22. Its manifest now records the actual diagnostic tags
and complete provincial scope rather than hardcoding22 everywhere.

All six cases conserve physical land, have zero historical area conflicts and
exactly preserve starting development, population, peasant employment and
building food. Neighbouring capacity, land and water assignments stay unchanged.
The paired audit also checks that shared overrides did not change.

The allocation adds4,491–5,584km² of inherited fields depending on the northern
boundary. Between11 and15 locations exhaust their modeled conversion budget.
That budget is an agronomic bound; it does not establish floodplain access or
independent water availability.

## Fresh world comparison

The middle boundary with HYDE weights is a representative probe, not a selected
winner. Both it and a fresh round49 baseline pass52 central horizon checks.
Their regional monthly/world checkpoint results reconcile. Outside the five
affected food-sharing provinces, every saved location checkpoint and every
annual provincial aggregate is exactly unchanged. No location gains additional
unmet-food months; the existing5,058 affected locations remain.

World population at100/200 is484.611m/523.080m versus484.154m/522.358m in the
baseline. These totals are diagnostic, not acceptance targets. Starting food
production remains fixed except in Qusiyya, where the existing land-bounded
slave-agriculture mechanism can employ additional workers and adds12.1653food
per month. Slave consumption is unchanged and unemployed slaves still do not
produce subsistence. Cookery/victuals and other observed building food are fixed.

## Why no allocation is adopted

The same regional source total produces an Aswan capacity range of27.642k to
395.217k across the six proxies: **14.30×**. Edfu spans5.81× and Kom Ombo3.92×.
The source-weight/boundary alternatives are therefore not locally interchangeable,
even though all survival screens pass. Choosing by population retention would
conceal this identification problem. Better basin/valley spatial evidence is
needed before treating one distribution as historical geography.

Primary engineering/cartographic sources have been located for follow-up:
[Willcocks1889 catalogue](https://ediscovery.qnl.qa/islandora/object/QNL%3A00013206)
and [Willcocks1904 text and plates](https://www.gutenberg.org/cache/epub/57379/pg57379-images.html).
The first catalogue confirms the1889 edition with maps, but its scan has not yet
been obtained. The later source must not transfer nineteenth-century perennial
irrigation into1337; it may help distinguish valley geometry and irrigation
types only with explicit temporal exclusions. Neither is claimed as a newly
completed spatial validation here.

## Reproduction and tests

For each boundary (`core`, `with_atfih_giza`, `with_cairo`) and weight method
(`hyde`, `luh2`), build the frozen input and run the canonical scenarios:

```sh
uv run python research/population_capacity/build_upper_nile_allocation.py --ledger artifacts/data/population_simulation/repair_round_49/world/starting_ledger.parquet --base-assignments research/population_capacity/historical_assignments_round_49.json --output artifacts/data/population_simulation/repair_round_51/with_atfih_giza_hyde/input --boundary with_atfih_giza --weights hyde
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments artifacts/data/population_simulation/repair_round_51/with_atfih_giza_hyde/input/assignments.json --output artifacts/data/population_simulation/repair_round_51/with_atfih_giza_hyde/simulation --regional-only --scenario-file research/population_capacity/round_37_source_replay_scenario.json --additional-tag aswan --additional-tag asyut --additional-tag minya --additional-tag el_bahnasa --override capacity.gaez_zero_development_fraction=4.5 --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/audit_upper_nile_allocations.py --root artifacts/data/population_simulation/repair_round_51 --baseline artifacts/data/population_simulation/repair_round_49/world/starting_ledger.parquet
uv run ppc test tests/test_regional_field_extent.py tests/test_historical_model.py -q
```

For the world pair, omit `--regional-only`, use outputs `baseline_world` and
`representative_world`, and select round49 versus the middle-boundary assignment.
The isolated-world auditor accepts `--allow-field-change` with the explicit20
target tags recorded in the input manifest; it verifies physical conservation
and the annual outside-province comparison as well as checkpoints.

Focused regressions: **27passed**, including seven new allocation tests. The last
full suite is still round49's867passed/1explained skip; no later full-suite claim
is made. No game export, building balance or live deployment occurred. Overall
historical, demographic, holdout, progression and resource acceptance stays open.
