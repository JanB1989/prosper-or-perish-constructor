# Round 45: Andean staple presence and reconciled food diagnosis

**Not accepted.** Cusco/Acamama now passes both central survival screens, bringing the regional result to40/44. Bali/Lombok and Trowulan remain failed. This run uses the same22 complete provinces,12 months of initial stocks, growth scenario and coefficients as round44. It does not certify other initial stocks, uncertainty, holdouts or the wider acceptance programme.

## Evidence and source correction

The pinned FAO *International Year of the Potato2008* account, printed pp.14–15 / PDF pp.4–5, describes pre-Inca Central Andean maize/potato systems and their continuation into the Inca period. `cusco_staple_presence_evidence.json` records an explicit regional availability inference for the nine existing Cusco-system locations. It does not claim nine dated field excavations. The Marcacocha primary palaeoecological record supplies additional local maize context. Neither the source's reconstructed potato yield nor its historical population estimates become calibration inputs.

The existing maize and white-potato crop keys change from uncertain to available. White-potato represents the existing Solanum tuberosum input; the source is not proof of modern cultivar performance. Physical climate, crop suitability, fallow, current hectares, infrastructure and the missing-yield treatment remain unchanged.

The rebuilt annual source changes808 rows in eight locations, with no changes outside the named scope. Pisaq's original zero crop support remains a flagged source gap with its existing explicit analogue; crop availability cannot invent a nonzero physical yield. Canonical capacity changes in the same eight locations. The audit confirms zero change in cultivated hectares, water-served hectares, development, population composition and building food.

## Measured outcome

| Cusco metric | Before | Corrected |
|---|---:|---:|
| Provincial population retention, year100 | 91.91% | 99.61% |
| Provincial population retention, year200 | 92.18% | 99.91% |
| Minimum location retention, year100 | 87.81% | 99.23% |
| Minimum location retention, year200 | 88.36% | 99.83% |
| Unmet location-months after startup |216|0|
| Starting monthly food balance |−30.469|+28.925|

Worst local early population retention is99.09%; development also passes. Total starting capacity rises by53.388 thousand people, distributed through the same existing physical components and development stacking. No location is fitted to population and no consumption coefficient changes.

## What the food accounts establish

Before this correction, all three failed provinces had positive non-subsistence balances after covering other population types: Bali +107.517, Trowulan +255.567 and Cusco +139.170 monthly food. Their deficits were peasant-pressure deficits, with no residual provincial deficit in the negligible-pressure diagnostic. This supports continued geographical diagnosis; it does not authorize assigning the artificial diagnostic capacity to the map.

The new reusable `audit_candidate_food_accounts.py` reproduces a saved candidate through canonical preparation, verifies its full starting ledger and provincial budgets, and exports actual/low-pressure accounts across every tested province. It was executed successfully on rounds44 and45. These audits retain food-building supply and record their limitations and fingerprints. Starting budgets alone do not prove long-run or historical acceptance.

## Reproduction

```sh
uv run python research/population_capacity/build_named_crop_history.py --evidence research/population_capacity/cusco_staple_presence_evidence.json --baseline-registry artifacts/data/population_capacity/repair_round_44/crop_history/crop_history_registry.toml --baseline-labels artifacts/data/population_capacity/repair_round_44/crop_history/crop_mode_labels.parquet --output artifacts/data/population_capacity/repair_round_45/crop_history --config-output population_capacity.round45.local.toml --annual-output artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios
uv run ppc population-capacity build-risk-scenarios --config population_capacity.round45.local.toml
uv run python research/population_capacity/compare_crop_history_scenarios.py --before artifacts/data/population_capacity/repair_round_44/crop_risk_scenarios/crop_system_scenarios.parquet --after artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet --output artifacts/data/population_capacity/repair_round_45 --name cusco_staple_presence
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_40.json --output artifacts/data/population_simulation/repair_round_45/source_only --regional-only --scenario-file research/population_capacity/round_37_source_replay_scenario.json --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/audit_candidate_food_accounts.py --experiment artifacts/data/population_simulation/repair_round_45/source_only
```

Artifacts live under `artifacts/data/population_capacity/repair_round_45` and `artifacts/data/population_simulation/repair_round_45`. Source attribution, food accounting and trajectory manifests are linked by `round_summary.json`. No accepted manifest, game export or live deployment has been produced.
