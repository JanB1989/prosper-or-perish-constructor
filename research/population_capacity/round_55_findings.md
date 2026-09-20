# Round 55: canonical historical-field recovery and component accounting

Status: both grouped candidates pass the focused100/200-year screens; world
comparison checked. No accepted-model claim or game export.

## Repair

Round54's allocation builder used a stricter land ceiling than the canonical
historical model. The model already allowed explicitly evidenced cultivation
beyond a crop-mixture denominator, recovering only the requested area from
known wild/grazing land and excluding unknown cover. The builder had retained
the older conversion-opportunity ceiling and rejected those assignments first.

The shared `known_land_for_evidenced_fields` calculation now supplies that
conditional budget to both paths. It does not declare all known land cultivable
or add unused land to future improvement opportunity. Footprint evidence and
water availability remain separate requirements. The default, non-evidenced
regional allocation retains its original stricter contract.

The corrected experiment also distinguishes the seasonal-basin component from
all cultivated fields. Its source component totals8,400km². Guza's260.2067km²
of existing fields above the proposed basin component are preserved separately,
with their hydraulic type unresolved. They are not newly added land, identified
berms, or imported nineteenth-century summer irrigation. Total assigned fields
are therefore8,660.2067km², not a silently altered8,400km² source observation.

The revised contract was frozen before the new allocation and simulations.
The old rejected contract/results remain available as round54.

## Focused outcomes

Both HYDE and LUH2 within-group weight variants pass52/52 checks across26
complete provinces at100/200: **104/104**. They have zero historical area
conflicts. Both conserve land, leave neighbours/development/observed food and
peasant employment unchanged, and do not enlarge unused physical opportunity.
The auditor checks every location's intended fields against the canonical
starting ledger and reconciles the basin component separately.

The two variants assign4,751.5466km² of additional inherited fields and serve
7,794.1860km² at central operational coverage. No location exhausts its
conditional known-land budget. This establishes accounting feasibility, not
hydrological proof of the assumed historical footprint.

Within these fixed historical groups, Aswan's capacity is23.857k–60.614k
(2.54×); Edfu50.053k–60.650k (1.21×), Kom Ombo125.033k–136.143k (1.09×),
and Esna233.555k–294.433k (1.26×). These remain scenario sensitivity ranges,
not confidence intervals. They do not cover the independent uncertainty in
historical group boundaries or transferring1889 basin shares to1337.

## Verification and remaining work

The fresh unchanged baseline reproduces all412 starting-state columns exactly
against round49. Extracting the shared recovery function does not rebalance
the world. Focused regression command:

```sh
uv run ppc test tests/test_grouped_nile_allocation.py tests/test_regional_field_extent.py tests/test_historical_model.py -q
```

Result: **32passed**. The new component/recovery fixture checks unknown-land
exclusion, preservation of excess existing fields and the independent basin
total. The last full suite remains round52's878passed/1explained skip.

The fresh unchanged/grouped world simulations both pass52central horizon
checks. Monthly provincial histories reproduce world checkpoints. Every saved
checkpoint and annual provincial aggregate outside the five affected Nile
provinces is exactly unchanged. No location gains unmet-food months; the
existing5,058 affected locations remain. World population is484.509m/522.925m
at100/200 versus484.154m/522.358m in the unchanged baseline. Those totals are
diagnostics, not targets. The isolated-world audit preserves all population
components, observed building food and peasant employment at the start.
The approximate historical groups and related HYDE/LUH2 weights still cannot
certify the independent historical/holdout gates. Remaining global acceptance
groups are not marked passed by these focused results.

## Reproduction

For each weight (`hyde`, `luh2`), use a fresh input directory:

```sh
uv run python research/population_capacity/build_upper_nile_allocation.py --ledger artifacts/data/population_simulation/repair_round_49/world/starting_ledger.parquet --base-assignments research/population_capacity/historical_assignments_round_49.json --output artifacts/data/population_simulation/repair_round_55/grouped_hyde/input --boundary with_cairo --weights hyde --group-contract research/population_capacity/upper_nile_grouped_accounting_experiment.json
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments artifacts/data/population_simulation/repair_round_55/grouped_hyde/input/assignments.json --output artifacts/data/population_simulation/repair_round_55/grouped_hyde/simulation --regional-only --scenario-file research/population_capacity/round_37_source_replay_scenario.json --additional-tag aswan --additional-tag asyut --additional-tag minya --additional-tag el_bahnasa --override capacity.gaez_zero_development_fraction=4.5 --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/audit_upper_nile_allocations.py --root artifacts/data/population_simulation/repair_round_55 --baseline artifacts/data/population_simulation/repair_round_49/world/starting_ledger.parquet --case grouped_hyde --case grouped_luh2
```

For the world pair, omit `--regional-only` and select round49 assignments versus
the grouped HYDE assignment, with outputs `baseline_world` and `grouped_world`.
Cookery/victuals output remains in the observed food account; neither urban
consumption nor slave consumption changes. No building balance or live deploy.
