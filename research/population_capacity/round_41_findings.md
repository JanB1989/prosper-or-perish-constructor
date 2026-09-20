# Round 41: dated rice presence in Malang

Status: **not accepted**. This corrects a source-coverage error but does not resolve Trowulan's food failure. The regional screen remains 36 passed and eight failed horizon checks.

## Evidence and canonical source change

[The pinned Christie evidence](malang_rice_presence_evidence.json) records historical rice in the named Malang cultivated landscape, including early conversion to wet fields. The explicit crosswalk selects `malang` only. It is not a fabricated archaeological coordinate, measured cultivated polygon, or expansion to all Java. Both crop water-mode keys receive rice-presence evidence; active irrigation, crop suitability and actual field extent remain separately constrained. No extra harvest is added: the chapter does not document double rice cropping before the fifteenth century.

The pipeline registry now accepts optional inline `system_evidence` records for this form of named-place attestation. Each requires a source checksum, dated attestation, locator, explicit location/crop crosswalk and geographic interpretation. Its identity enters the existing registry hash. Conflicting point/domain evidence remains unresolved rather than being overridden. Old point mapping and regional domain contracts are preserved; no population or yield field is permitted in these records.

The source compiler replays the existing South American crop-history correction before adding Malang. Exactly two availability entries move from 0.5 to 1: `rice_dry` and `rice_wet` in Malang. Every other availability entry and all physical label inputs are unchanged. The annual rebuild covers 20,929 locations, 64 physical samples per location and 101 shared years (2,113,829 rows). Its paired comparison changes exactly 101 rows, all in Malang; zero outside-scope changes occur.

## Simulation result

The comparison retains round-38 historical assignments, including the original Lombok assessment, to isolate rice presence from the separate round-40 management trial. Scale, area exponent, subsistence output, consumption and growth/development scenario remain unchanged.

Malang keeps 48.634 km² of cultivated fields, 24.317 km² of water-managed fields and development 57.5. Its capacity rises from 18.130k to 20.044k. Every other location's starting capacity, development, fields, water-managed area, building food and population is identical. All-location fields, development, food buildings and population are unchanged.

Trowulan province retains 69.96% of population at year 100 and 70.31% at year 200, versus roughly 69.08%/69.43% previously. It still has 385 unmet location-months after startup and fails both horizons. The correction is warranted by crop evidence, not selected for survival. It explains only a small part of the province's shortage and must not be amplified into a fitted yield multiplier.

## Verification and reproduction

48 focused regressions pass, including source identity, explicit-scope behaviour, unknown location rejection, postdated/corrupt source rejection, conflict preservation, annual crop units and pipeline compatibility. The earlier full-suite result is not a final validation of this changed pipeline; the final full suite remains required when the candidate is ready.

```sh
uv run python research/population_capacity/build_named_crop_history.py --evidence research/population_capacity/malang_rice_presence_evidence.json --baseline-registry artifacts/data/population_capacity/repair_round_37/crop_history/crop_history_registry.toml --baseline-labels artifacts/data/population_capacity/repair_round_37/crop_history/crop_mode_labels.parquet --output artifacts/data/population_capacity/repair_round_41/crop_history --config-output population_capacity.round41.local.toml --annual-output artifacts/data/population_capacity/repair_round_41/crop_risk_scenarios
uv run ppc population-capacity build-risk-scenarios --config population_capacity.round41.local.toml
uv run python research/population_capacity/compare_crop_history_scenarios.py --before artifacts/data/population_capacity/repair_round_37/crop_risk_scenarios/crop_system_scenarios.parquet --after artifacts/data/population_capacity/repair_round_41/crop_risk_scenarios/crop_system_scenarios.parquet --output artifacts/data/population_capacity/repair_round_41 --name malang_rice_presence
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_38.json --output artifacts/data/population_simulation/repair_round_41/malang_rice --scenario-file research/population_capacity/round_37_source_replay_scenario.json --regional-only --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_41/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run ppc test tests/test_population_capacity_config.py tests/test_annual_crop.py ../ProsperOrPerishPopulationCapacityPipeline/tests/test_crop_history.py ../ProsperOrPerishPopulationCapacityPipeline/tests/test_pyaez_trace_fallback.py -q
```

Source artifacts are in `artifacts/data/population_capacity/repair_round_41`; simulation, monthly histories, budgets and the source-isolation check are in `artifacts/data/population_simulation/repair_round_41/malang_rice`. No crop-presence correction is a claim of model acceptance, legal infrastructure maxima or game-export readiness. No export or deployment occurred.
