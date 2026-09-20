# Round 47: shared scale, broad regional passes and global failures

**Model not accepted.** Scale4.5 passes the central regional programme and the broader stock/development screens. The world run exposes source/assignment gaps that those regional passes cannot certify.

## Shared physical-to-game scale

The scale comparison freezes cultivated hectares, development assessments, infrastructure types, area exponent0.75, development coefficient0.05 and subsistence output1.3. Only the common physical support conversion changes. It is not a per-location capacity fit or additional physical land.

| Shared scale | Regional horizon checks passed | Bali P100/P200 | Trowulan P100/P200 |
|---|---:|---:|---:|
|3.0|40/44|76.66% /77.18%|77.07% /77.40%|
|3.5|40/44|83.32% /83.81%|83.79% /84.10%|
|4.0|43/44|89.49% /90.07%|90.16% /90.54%|
|4.5|44/44|95.28% /95.99%|96.22% /96.65%|

All scale4.5 central checks have zero unmet food after startup. The higher scale is a candidate for wider testing, not accepted solely because its survival count is favourable. `comparison_contract.json` was written before running this comparison.

## Broader regional programme

The broad candidate combines scale4.5, round45 annual crop evidence and the documented central southern lake-management assignment from round43. It retains every other coefficient and assignment. Monthly histories cover124 locations in22 complete provinces. All352 geographical horizon checks pass across stocks0/3/12/24, paired production shocks and frozen/coupled development. Sixteen paired food-control checks and two experimental land-activation checks also pass. The latter are controlled experiments, not proof of historically dated investment schedules.

Saved states, population components and checkpoint coverage reconcile; no historical area conflicts are present. The evaluated register still reports unresolved historical criteria, holdouts, complete economic/mechanical coverage, physical maxima and sensitivity. The older recovery artifact is not automatically attached to this changed candidate.

## World run: why acceptance remains open

The complete world run includes20,929 locations, annual aggregate histories and checkpoints matching the monthly regional runs within the runner's export/replay tolerance.

| Year | Population, millions | Capacity, millions | Mean development |
|---|---:|---:|---:|
|0|394.50|1,654.39|27.56|
|25|400.10|1,666.44|27.80|
|100|484.04|1,711.75|28.80|
|200|522.13|1,757.11|29.91|

These totals are diagnostic, not historical population targets. **5,058 locations experience unmet food.** Large starting consumption outliers occur in Jaisalmer, northern Sindh, Cholistan and Arabian provinces. They have no residual provincial deficit in the negligible-pressure diagnostic; capacity/source failures can therefore dominate the food result despite a favourable world total.

`current_fields_missing_water_diagnosis.csv` identifies589 locations in180 provinces with positive reconstructed current fields, zero annual rainfed support, positive irrigated support and zero assigned water service. They contain14,371.15 km² of fields. This is an evidence conflict, not proof of zero historical agriculture and not permission to grant irrigation indiscriminately. The largest groups are Arabia273 locations, Maghreb59, Persia55 and Sahel32. Historical water-dependent systems and source spatial allocation must be reconciled without fitting to population.

The map also exposes1,537 locations with development25 or higher assigned from agricultural archetypes despite zero dated cropland in both related land reconstructions;1,535 use the open-field cereal archetype. `agricultural_management_without_dated_fields.csv` records this warning. Zero reconstructed land does not prove historical absence, but a potential crop classification cannot establish intensive historical management. Named-system evidence and explicit livelihood assumptions must resolve this classification issue.

## Paired global baseline

A second complete world run holds the round43 assignments, round45 crop source, coefficients and scenario fixed at scale3.0. At years25/100/200, the scale4.5 candidate has no location with more cumulative unmet-food months. By year200,3,515 locations have fewer such months; the count of locations ever affected falls from5,619 to5,058. Baseline population is442.72m/467.19m at100/200 versus484.04m/522.13m in the candidate. The paired checkpoints cover all20,929 locations and are saved in scale_world_paired_checkpoints.parquet. This shows reduced scarcity under the tested scale; it does not certify the remaining cases or historical carrying densities.

## Artifacts and reproduction

All artifacts are under `artifacts/data/population_simulation/repair_round_47`. `acceptance/evaluated_criteria_register.md` and `evaluated_horizon_criteria.csv` retain group versus case distinctions. Candidate point maps and provincial retention plots consume the canonical ledger and saved histories; they are explicitly labelled unaccepted. The reusable renderer now accepts an output directory and writes an input fingerprint. The candidate map was visually inspected.

```sh
# The central scale comparison uses assignments_round_40; repeat with scales3.5/4.0/4.5.
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_40.json --output artifacts/data/population_simulation/repair_round_47/scale_4_5 --regional-only --scenario-file research/population_capacity/round_37_source_replay_scenario.json --override capacity.gaez_zero_development_fraction=4.5 --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/run_acceptance_round_25.py --assignments research/population_capacity/historical_assignments_round_43.json --output artifacts/data/population_simulation/repair_round_47/acceptance --scenario-file research/population_capacity/round_37_source_replay_scenario.json --scenario common_slower_quarter --include-frozen --override capacity.gaez_zero_development_fraction=4.5 --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_43.json --output artifacts/data/population_simulation/repair_round_47/world --scenario-file research/population_capacity/round_37_source_replay_scenario.json --override capacity.gaez_zero_development_fraction=4.5 --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/summarize_acceptance_evidence.py --output artifacts/data/population_simulation/repair_round_47/acceptance
uv run python research/population_capacity/render_acceptance_round_25.py --output artifacts/data/population_simulation/repair_round_47/acceptance
```

No accepted manifest, game export or live deployment is produced. All remaining physical, historical, population-composition and global acceptance requirements remain in scope.
